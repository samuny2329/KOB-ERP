"""Closed-loop auto-creators: turn `thiti.plan.replenishment` proposals into
actual Odoo draft documents (purchase.order, mrp.production, stock.picking).

Only **drafts** are ever created. Buyers/planners must explicitly confirm
each document. Confirmed/sent docs from previous runs are never touched.

Idempotency:
- Every auto-created doc is tagged `origin = "THITI/<run.name>"`
- Re-running the same plan first cancels prior `state='draft'` docs that
  share the same origin (config `thiti.delete_obsolete_drafts`)
- Each replenishment record stores the created doc ID for audit/jump
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class ThitiAutoCreator(models.AbstractModel):
    _name = "thiti.auto.creator"
    _description = "Thiti Auto-creator (plan output → Odoo draft docs)"

    @api.model
    def create_all(self, run) -> dict[str, int]:
        params = self.env["ir.config_parameter"].sudo()
        flags = {
            "po": params.get_param("thiti.auto_create_po", "True") == "True",
            "mo": params.get_param("thiti.auto_create_mo", "True") == "True",
            "do": params.get_param("thiti.auto_create_do", "False") == "True",
        }
        horizons = {
            "po": int(params.get_param("thiti.po_horizon_days", 30)),
            "mo": int(params.get_param("thiti.mo_horizon_days", 14)),
            "do": int(params.get_param("thiti.do_horizon_days", 7)),
        }
        cleanup = params.get_param("thiti.delete_obsolete_drafts", "True") == "True"
        origin = f"THITI/{run.name}"

        if cleanup:
            self._cleanup_obsolete_drafts(origin)

        proposals = self._build_proposals(run, flags, horizons, origin)
        if proposals:
            self.env["thiti.plan.replenishment"].create(proposals)

        counts = {"po": 0, "mo": 0, "do": 0}
        if flags["po"]:
            counts["po"] = self._create_purchase_orders(run, origin)
        if flags["mo"]:
            counts["mo"] = self._create_manufacturing_orders(run, origin)
        if flags["do"]:
            counts["do"] = self._create_distribution_pickings(run, origin)
        return counts

    def _cleanup_obsolete_drafts(self, origin: str) -> None:
        po_drafts = self.env["purchase.order"].search([
            ("origin", "=", origin),
            ("state", "=", "draft"),
        ])
        for po in po_drafts:
            po.button_cancel()
            po.unlink()
        mo_drafts = self.env["mrp.production"].search([
            ("origin", "=", origin),
            ("state", "=", "draft"),
        ])
        mo_drafts.unlink()
        picking_drafts = self.env["stock.picking"].search([
            ("origin", "=", origin),
            ("state", "=", "draft"),
        ])
        picking_drafts.unlink()
        if po_drafts or mo_drafts or picking_drafts:
            _logger.info(
                "Cleanup origin=%s: %s PO + %s MO + %s picking drafts canceled",
                origin, len(po_drafts), len(mo_drafts), len(picking_drafts),
            )

    def _build_proposals(self, run, flags, horizons, origin) -> list[dict]:
        """Materialise thiti.plan.replenishment from thiti.plan.operation."""
        today = fields.Datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        ops = self.env["thiti.plan.operation"].search([
            ("run_id", "=", run.id),
            ("op_type", "in", [k for k, v in flags.items() if v]),
        ])
        proposals: list[dict] = []
        for op in ops:
            kind = op.op_type
            horizon = horizons.get(kind, 30)
            cutoff = today + timedelta(days=horizon)
            if op.start_datetime and op.start_datetime > cutoff:
                continue
            proposals.append({
                "run_id": run.id,
                "plan_operation_id": op.id,
                "kind": kind,
                "item_id": op.item_id.id if op.item_id else False,
                "product_id": op.product_id.id if op.product_id else False,
                "location_id": op.location_id.id if op.location_id else False,
                "warehouse_id": op.location_id.warehouse_id.id if op.location_id else False,
                "bom_id": op.bom_id.id if op.bom_id else False,
                "quantity": op.quantity,
                "scheduled_date": op.start_datetime,
                "due_date": op.end_datetime,
                "origin": origin,
                "state": "proposed",
            })
        return proposals

    def _resolve_product(self, item) -> "models.Model":
        if not item:
            return self.env["product.product"]
        product = self.env["product.product"].search(
            [("default_code", "=", item.name)], limit=1,
        )
        return product

    def _resolve_partner(self, supplier) -> "models.Model":
        if not supplier or not supplier.partner_id:
            return self.env["res.partner"]
        return supplier.partner_id

    # ---- Purchase ----
    def _create_purchase_orders(self, run, origin: str) -> int:
        reps = self.env["thiti.plan.replenishment"].search([
            ("run_id", "=", run.id),
            ("kind", "=", "po"),
            ("state", "=", "proposed"),
        ])
        groups: dict[tuple, list] = defaultdict(list)
        for rep in reps:
            partner = self._resolve_partner(rep.supplier_id)
            product = rep.product_id or self._resolve_product(rep.item_id)
            if not partner or not product:
                rep.write({"state": "canceled",
                           "error_message": "Missing partner or product"})
                continue
            week_key = rep.scheduled_date.isocalendar() if rep.scheduled_date else (0, 0)
            groups[(partner.id, week_key[0], week_key[1])].append((rep, product, partner))

        created = 0
        for (partner_id, _yr, _wk), batch in groups.items():
            order_vals = {
                "partner_id": partner_id,
                "origin": origin,
                "date_order": fields.Datetime.now(),
                "order_line": [],
            }
            min_date = min((r.scheduled_date for r, *_ in batch
                            if r.scheduled_date), default=fields.Datetime.now())
            for rep, product, partner in batch:
                order_vals["order_line"].append((0, 0, {
                    "product_id": product.id,
                    "name": product.display_name,
                    "product_qty": rep.quantity,
                    "product_uom_id": product.uom_po_id.id,
                    "price_unit": product.standard_price or 0.0,
                    "date_planned": rep.scheduled_date or min_date,
                }))
            try:
                po = self.env["purchase.order"].create(order_vals)
                for (rep, product, partner), line in zip(batch, po.order_line):
                    rep.write({
                        "state": "created",
                        "purchase_order_id": po.id,
                        "purchase_order_line_id": line.id,
                    })
                created += 1
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Auto PO create failed: %s", exc)
                for rep, *_ in batch:
                    rep.write({"state": "canceled", "error_message": str(exc)[:500]})
        return created

    # ---- Manufacturing ----
    def _create_manufacturing_orders(self, run, origin: str) -> int:
        reps = self.env["thiti.plan.replenishment"].search([
            ("run_id", "=", run.id),
            ("kind", "=", "mo"),
            ("state", "=", "proposed"),
        ])
        created = 0
        for rep in reps:
            product = rep.product_id or self._resolve_product(rep.item_id)
            if not product:
                rep.write({"state": "canceled", "error_message": "No product"})
                continue
            bom = rep.bom_id or self.env["mrp.bom"]._bom_find(
                product, company_id=run.company_id.id,
            ).get(product)
            if not bom:
                rep.write({"state": "canceled", "error_message": "No BOM"})
                continue
            try:
                mo = self.env["mrp.production"].create({
                    "product_id": product.id,
                    "product_qty": rep.quantity,
                    "product_uom_id": product.uom_id.id,
                    "bom_id": bom.id,
                    "date_start": rep.scheduled_date or fields.Datetime.now(),
                    "origin": origin,
                })
                rep.write({"state": "created", "production_id": mo.id})
                created += 1
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Auto MO create failed: %s", exc)
                rep.write({"state": "canceled", "error_message": str(exc)[:500]})
        return created

    # ---- Distribution ----
    def _create_distribution_pickings(self, run, origin: str) -> int:
        reps = self.env["thiti.plan.replenishment"].search([
            ("run_id", "=", run.id),
            ("kind", "=", "do"),
            ("state", "=", "proposed"),
        ])
        groups: dict[tuple, list] = defaultdict(list)
        for rep in reps:
            src = rep.source_warehouse_id
            dst = rep.warehouse_id
            if not src or not dst:
                rep.write({"state": "canceled",
                           "error_message": "Missing source/dest warehouse"})
                continue
            day = rep.scheduled_date.date() if rep.scheduled_date else fields.Date.today()
            groups[(src.id, dst.id, day)].append(rep)

        created = 0
        for (src_id, dst_id, day), batch in groups.items():
            src = self.env["stock.warehouse"].browse(src_id)
            dst = self.env["stock.warehouse"].browse(dst_id)
            picking_type = self.env["stock.picking.type"].search([
                ("code", "=", "internal"),
                ("warehouse_id", "=", dst_id),
            ], limit=1)
            if not picking_type:
                for rep in batch:
                    rep.write({"state": "canceled",
                               "error_message": "No internal picking type for dest WH"})
                continue
            picking_vals = {
                "picking_type_id": picking_type.id,
                "location_id": src.lot_stock_id.id,
                "location_dest_id": dst.lot_stock_id.id,
                "origin": origin,
                "scheduled_date": fields.Datetime.now(),
                "move_ids_without_package": [],
            }
            for rep in batch:
                product = rep.product_id or self._resolve_product(rep.item_id)
                if not product:
                    continue
                picking_vals["move_ids_without_package"].append((0, 0, {
                    "name": product.display_name,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": rep.quantity,
                    "location_id": src.lot_stock_id.id,
                    "location_dest_id": dst.lot_stock_id.id,
                }))
            if not picking_vals["move_ids_without_package"]:
                continue
            try:
                picking = self.env["stock.picking"].create(picking_vals)
                for rep, move in zip(batch, picking.move_ids_without_package):
                    rep.write({"state": "created", "picking_id": picking.id})
                created += 1
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Auto picking create failed: %s", exc)
                for rep in batch:
                    rep.write({"state": "canceled", "error_message": str(exc)[:500]})
        return created
