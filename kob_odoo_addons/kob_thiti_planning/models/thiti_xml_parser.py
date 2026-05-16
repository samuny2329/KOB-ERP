"""Parse frePPLe output XML → thiti.plan.* records.

frePPLe writes the solved plan back as an XML tree mirroring the input
schema, with `<operationplans>` containing each planned op (purchase,
manufacture, distribute, deliver), `<demands>` annotated with pegged
operationplans, `<resources>` with `<loadplans>` per bucket, `<buffers>`
with `<flowplans>` projection, and `<problems>` listing infeasibilities.

This parser is tolerant to schema drift: missing optional tags are skipped,
unknown tags are ignored. Robust against partial outputs (e.g. timeout).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from lxml import etree

from odoo import api, models


_logger = logging.getLogger(__name__)


def _parse_dt(text: str | None) -> datetime | bool:
    if not text:
        return False
    try:
        return datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False


def _parse_float(text: str | None) -> float:
    try:
        return float(text) if text else 0.0
    except (ValueError, TypeError):
        return 0.0


def _child_text(el, tag: str) -> str:
    child = el.find(tag)
    return child.text if child is not None and child.text else ""


def _named_child(el, tag: str) -> str:
    """Return the <name> sub-element of <tag>, e.g. <item><name>X</name></item>."""
    child = el.find(tag)
    if child is None:
        return ""
    name_el = child.find("name")
    return name_el.text if name_el is not None and name_el.text else ""


class ThitiXmlParser(models.AbstractModel):
    _name = "thiti.xml.parser"
    _description = "Thiti XML Parser (frePPLe output → Odoo records)"

    @api.model
    def parse(self, run, output_xml: bytes) -> dict[str, int]:
        if not output_xml:
            return {"operations": 0, "pegs": 0, "loads": 0, "buffers": 0, "problems": 0}

        try:
            root = etree.fromstring(output_xml)
        except etree.XMLSyntaxError as exc:
            _logger.error("Output XML parse failed: %s", exc)
            raise

        # Clear previous outputs for this run
        self.env["thiti.plan.operation"].search([("run_id", "=", run.id)]).unlink()
        self.env["thiti.plan.demand.peg"].search([("run_id", "=", run.id)]).unlink()
        self.env["thiti.plan.resource.load"].search([("run_id", "=", run.id)]).unlink()
        self.env["thiti.plan.buffer.projection"].search([("run_id", "=", run.id)]).unlink()
        self.env["thiti.plan.problem"].search([("run_id", "=", run.id)]).unlink()

        counts = {
            "operations": self._parse_operationplans(run, root),
            "pegs": self._parse_pegging(run, root),
            "loads": self._parse_loadplans(run, root),
            "buffers": self._parse_buffer_projection(run, root),
            "problems": self._parse_problems(run, root),
        }
        _logger.info("Parsed plan output for run %s: %s", run.name, counts)
        return counts

    def _parse_operationplans(self, run, root) -> int:
        records: list[dict[str, Any]] = []
        item_idx = self._index_thiti("thiti.item", "name")
        location_idx = self._index_thiti("thiti.location", "name")
        resource_idx = self._index_thiti("thiti.resource", "name")
        op_type_lookup = {
            "PO": "po", "MO": "mo", "DO": "do", "DLVR": "dlvr",
        }
        for el in root.iter("operationplan"):
            reference = _child_text(el, "reference")
            op_name = _child_text(el, "operation") or _named_child(el, "operation")
            ordertype = _child_text(el, "ordertype")
            item_name = _named_child(el, "item")
            location_name = _named_child(el, "location")
            resource_name = _named_child(el, "resource")
            records.append({
                "run_id": run.id,
                "reference": reference,
                "operation_name": op_name,
                "op_type": op_type_lookup.get(ordertype),
                "item_id": item_idx.get(item_name) if item_name else False,
                "location_id": location_idx.get(location_name) if location_name else False,
                "resource_id": resource_idx.get(resource_name) if resource_name else False,
                "quantity": _parse_float(_child_text(el, "quantity")),
                "start_datetime": _parse_dt(_child_text(el, "start")),
                "end_datetime": _parse_dt(_child_text(el, "end")),
                "status": _child_text(el, "status") or "proposed",
                "criticality": _parse_float(_child_text(el, "criticality")),
                "delay_days": _parse_float(_child_text(el, "delay")) / 86400.0,
            })
        if records:
            self.env["thiti.plan.operation"].create(records)
        return len(records)

    def _parse_pegging(self, run, root) -> int:
        records: list[dict[str, Any]] = []
        demand_idx = self._index_thiti("thiti.demand", "name")
        item_idx = self._index_thiti("thiti.item", "name")
        location_idx = self._index_thiti("thiti.location", "name")
        for demand_el in root.iter("demand"):
            demand_name = _child_text(demand_el, "name")
            if not demand_name:
                continue
            item_name = _named_child(demand_el, "item")
            location_name = _named_child(demand_el, "location")
            pegs = demand_el.find("pegging")
            if pegs is None:
                continue
            for peg in pegs.iter("pegging"):
                op_ref = _child_text(peg, "operationplan") or _named_child(peg, "operationplan")
                records.append({
                    "run_id": run.id,
                    "demand_name": demand_name,
                    "demand_id": demand_idx.get(demand_name),
                    "operation_reference": op_ref,
                    "item_id": item_idx.get(item_name) if item_name else False,
                    "location_id": location_idx.get(location_name) if location_name else False,
                    "quantity": _parse_float(_child_text(peg, "quantity")),
                    "plan_end": _parse_dt(_child_text(peg, "end")),
                    "level": int(_parse_float(_child_text(peg, "level"))),
                })
        if records:
            self.env["thiti.plan.demand.peg"].create(records)
        return len(records)

    def _parse_loadplans(self, run, root) -> int:
        records: list[dict[str, Any]] = []
        resource_idx = self._index_thiti("thiti.resource", "name")
        for res_el in root.iter("resource"):
            resource_name = _child_text(res_el, "name")
            if not resource_name:
                continue
            plans = res_el.find("loadplans")
            if plans is None:
                continue
            for lp in plans.iter("loadplan"):
                records.append({
                    "run_id": run.id,
                    "resource_id": resource_idx.get(resource_name),
                    "bucket_start": _parse_dt(_child_text(lp, "startdate")),
                    "bucket_end": _parse_dt(_child_text(lp, "enddate")),
                    "available_hours": _parse_float(_child_text(lp, "available")),
                    "loaded_hours": _parse_float(_child_text(lp, "load")),
                    "setup_hours": _parse_float(_child_text(lp, "setup")),
                    "units_processed": _parse_float(_child_text(lp, "units")),
                })
        if records:
            self.env["thiti.plan.resource.load"].create(records)
        return len(records)

    def _parse_buffer_projection(self, run, root) -> int:
        records: list[dict[str, Any]] = []
        item_idx = self._index_thiti("thiti.item", "name")
        location_idx = self._index_thiti("thiti.location", "name")
        buffer_idx = {
            (b.item_id.name, b.location_id.name): b.id
            for b in self.env["thiti.buffer"].search([])
            if b.item_id and b.location_id
        }
        for buf_el in root.iter("buffer"):
            buf_name = _child_text(buf_el, "name")
            item_name = _named_child(buf_el, "item")
            location_name = _named_child(buf_el, "location")
            plans = buf_el.find("flowplans")
            if plans is None:
                continue
            for fp in plans.iter("flowplan"):
                records.append({
                    "run_id": run.id,
                    "buffer_id": buffer_idx.get((item_name, location_name)),
                    "item_id": item_idx.get(item_name) if item_name else False,
                    "location_id": location_idx.get(location_name) if location_name else False,
                    "bucket_start": _parse_dt(_child_text(fp, "date")),
                    "start_onhand": _parse_float(_child_text(fp, "onhand_before")),
                    "consumed": _parse_float(_child_text(fp, "consumed")),
                    "produced": _parse_float(_child_text(fp, "produced")),
                    "end_onhand": _parse_float(_child_text(fp, "onhand")),
                })
        if records:
            self.env["thiti.plan.buffer.projection"].create(records)
        return len(records)

    def _parse_problems(self, run, root) -> int:
        records: list[dict[str, Any]] = []
        severity_lookup = {
            "info": "info", "warning": "warning",
            "error": "error", "critical": "critical",
        }
        for prob in root.iter("problem"):
            entity_kind = _child_text(prob, "entity") or "operation"
            kind_norm = entity_kind.lower()
            if kind_norm not in ("demand", "buffer", "resource", "operation"):
                kind_norm = "operation"
            records.append({
                "run_id": run.id,
                "problem_type": _child_text(prob, "name") or "unknown",
                "severity": severity_lookup.get(
                    _child_text(prob, "severity") or "", "warning",
                ),
                "entity_kind": kind_norm,
                "entity_name": _child_text(prob, "owner") or _named_child(prob, "owner"),
                "start_datetime": _parse_dt(_child_text(prob, "start")),
                "end_datetime": _parse_dt(_child_text(prob, "end")),
                "weight": _parse_float(_child_text(prob, "weight")),
                "description": _child_text(prob, "description"),
            })
        if records:
            self.env["thiti.plan.problem"].create(records)
        return len(records)

    def _index_thiti(self, model: str, field: str) -> dict[str, int]:
        recs = self.env[model].search([])
        return {getattr(r, field): r.id for r in recs if getattr(r, field)}
