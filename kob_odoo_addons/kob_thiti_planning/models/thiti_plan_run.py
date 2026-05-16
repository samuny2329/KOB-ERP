from __future__ import annotations

import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


PLAN_STATE = [
    ("draft", "Draft"),
    ("collecting", "Collecting"),
    ("solving", "Solving"),
    ("parsing", "Parsing"),
    ("done", "Done"),
    ("failed", "Failed"),
    ("canceled", "Canceled"),
]

CONSTRAINT_LEVEL = [
    ("0", "Unconstrained"),
    ("7", "Material only"),
    ("13", "Lead-time + material"),
    ("15", "Full (material + capacity + lead-time)"),
]

PLAN_TYPE = [
    ("1", "Constrained Plan (MRP)"),
    ("2", "Unconstrained Plan (MPS)"),
]


class ThitiPlanRun(models.Model):
    _name = "thiti.plan.run"
    _description = "Thiti Planning Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        required=True, index=True, tracking=True,
        default=lambda s: s._default_name(),
    )
    state = fields.Selection(PLAN_STATE, default="draft", required=True, tracking=True)
    plan_horizon_days = fields.Integer(default=90, tracking=True)
    constraint_level = fields.Selection(
        CONSTRAINT_LEVEL, default="15", required=True, tracking=True,
    )
    plan_type = fields.Selection(PLAN_TYPE, default="1", required=True, tracking=True)
    plan_currentdate = fields.Datetime(
        default=fields.Datetime.now, tracking=True,
        help="Reference 'now' passed to the solver — defaults to record creation time.",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
        required=True, index=True, tracking=True,
    )
    warehouse_ids = fields.Many2many(
        "stock.warehouse", string="Warehouses (empty = all)",
    )
    scenario_id = fields.Many2one(
        "thiti.scenario", string="Scenario", index=True,
        ondelete="set null",
    )
    user_id = fields.Many2one(
        "res.users", default=lambda s: s.env.user, tracking=True,
    )
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    duration_seconds = fields.Float(readonly=True)

    item_count = fields.Integer(readonly=True)
    location_count = fields.Integer(readonly=True)
    buffer_count = fields.Integer(readonly=True)
    operation_count = fields.Integer(readonly=True)
    resource_count = fields.Integer(readonly=True)
    demand_count = fields.Integer(readonly=True)
    supplier_count = fields.Integer(readonly=True)

    log = fields.Text(readonly=True)
    error_message = fields.Text(readonly=True)
    input_xml_attachment_id = fields.Many2one(
        "ir.attachment", string="Input XML", readonly=True,
    )
    output_xml_attachment_id = fields.Many2one(
        "ir.attachment", string="Output XML", readonly=True,
    )

    @api.model
    def _default_name(self) -> str:
        return _("Plan / %s") % fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def action_run(self):
        """Trigger full pipeline (collect → solve → parse → auto-create).

        Phase 4 implements `_collect()` only. Phases 5-6 add the rest.
        """
        for rec in self:
            rec._run_pipeline()

    def action_collect_preview(self):
        """Collect Odoo data, serialize to frePPLe XML, attach. No solver."""
        self.ensure_one()
        if self.state in ("collecting", "solving", "parsing"):
            raise UserError(_("Plan already in progress."))
        self.write({
            "state": "collecting",
            "started_at": fields.Datetime.now(),
            "error_message": False,
        })
        t0 = time.monotonic()
        collector = self.env["thiti.data.collector"]
        try:
            data = collector.collect(self)
            xml_bytes = self.env["thiti.xml.serializer"].serialize(
                data,
                plan_type=self.plan_type or "1",
                constraint=self.constraint_level or "15",
                loglevel=1,
            )
            attachment = self.env["ir.attachment"].create({
                "name": f"thiti_input_{self.id}.xml",
                "type": "binary",
                "datas": xml_bytes and __import__("base64").b64encode(xml_bytes),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/xml",
            })
            counts = data.get("_counts", {})
            self.write({
                "input_xml_attachment_id": attachment.id,
                "item_count": counts.get("items", 0),
                "location_count": counts.get("locations", 0),
                "buffer_count": counts.get("buffers", 0),
                "operation_count": counts.get("operations", 0),
                "resource_count": counts.get("resources", 0),
                "demand_count": counts.get("demands", 0),
                "supplier_count": counts.get("suppliers", 0),
                "state": "draft",
                "duration_seconds": time.monotonic() - t0,
                "finished_at": fields.Datetime.now(),
                "log": (self.log or "") + "\n" + _("Collected: %s") % counts,
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Collect & Preview"),
                    "message": _("Generated XML: %s bytes (%s items, %s demands).") % (
                        len(xml_bytes), counts.get("items", 0), counts.get("demands", 0),
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as exc:  # noqa: BLE001 — surface any collector failure
            _logger.exception("Collect & Preview failed for plan run %s", self.id)
            self.write({
                "state": "failed",
                "error_message": str(exc),
                "duration_seconds": time.monotonic() - t0,
                "finished_at": fields.Datetime.now(),
            })
            raise

    def _run_pipeline(self):
        """Collect → serialize XML → solver → parse output → store records.

        Phase 5 wires solver subprocess + output parser.
        Phase 6 will append auto-create PO/MO/DO drafts.
        """
        self.ensure_one()
        import base64

        self.action_collect_preview()
        if not self.input_xml_attachment_id:
            return
        input_xml = base64.b64decode(self.input_xml_attachment_id.datas)

        self.write({"state": "solving", "started_at": fields.Datetime.now()})
        t0 = time.monotonic()
        try:
            result = self.env["thiti.solver.wrapper"].run(
                input_xml,
                plan_type=self.plan_type or "1",
                constraint=self.constraint_level or "15",
                loglevel=1,
            )
        except Exception as exc:  # noqa: BLE001 — surface engine failures
            _logger.exception("Solver failed for run %s", self.id)
            self.write({
                "state": "failed",
                "error_message": str(exc),
                "duration_seconds": time.monotonic() - t0,
                "finished_at": fields.Datetime.now(),
            })
            raise

        output_xml = result.get("output_xml") or b""
        log_extra = (
            f"Solver returncode={result.get('returncode')} "
            f"stdout_len={len(result.get('stdout',''))} "
            f"output_len={len(output_xml)}"
        )
        attachment = self.env["ir.attachment"].create({
            "name": f"thiti_output_{self.id}.xml",
            "type": "binary",
            "datas": base64.b64encode(output_xml or b""),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/xml",
        })
        self.output_xml_attachment_id = attachment.id

        if result.get("returncode") != 0:
            self.write({
                "state": "failed",
                "error_message": (
                    (result.get("stderr") or "") + "\n" + (result.get("stdout") or "")
                )[:8000],
                "duration_seconds": time.monotonic() - t0,
                "finished_at": fields.Datetime.now(),
                "log": (self.log or "") + "\n" + log_extra,
            })
            return

        self.write({"state": "parsing"})
        counts = self.env["thiti.xml.parser"].parse(self, output_xml)

        created = self.env["thiti.auto.creator"].create_all(self)
        kpi = self.env["thiti.kpi"].recompute_for_run(self)

        self.write({
            "state": "done",
            "duration_seconds": time.monotonic() - t0,
            "finished_at": fields.Datetime.now(),
            "log": (self.log or "") + "\n" + log_extra
                   + "\nParsed: %s\nDrafts: %s\nKPI: SL=%.1f%% util=%.1f%%" % (
                       counts, created, kpi.service_level_pct, kpi.capacity_utilization_pct,
                   ),
        })
        # TODO Phase 6: auto-create PO/MO/DO drafts.
