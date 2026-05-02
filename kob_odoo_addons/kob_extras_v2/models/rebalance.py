# -*- coding: utf-8 -*-
"""Phase 34 — Multi-warehouse stock rebalancing engine."""
from odoo import api, fields, models


class KobRebalanceProposal(models.Model):
    _name = "kob.rebalance.proposal"
    _description = "Stock Rebalance Proposal"
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    product_id = fields.Many2one("product.product", required=True)
    source_location_id = fields.Many2one(
        "stock.location", required=True, string="From",
    )
    dest_location_id = fields.Many2one(
        "stock.location", required=True, string="To",
    )
    qty_proposed = fields.Float(required=True)
    reason = fields.Selection(
        [
            ("oversupply", "Source Oversupply"),
            ("understock", "Destination Understock"),
            ("expiring", "Lot Expiring at Source"),
            ("velocity", "Velocity Mismatch"),
            ("manual", "Manual Trigger"),
        ],
        default="manual",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("transferred", "Transferred"),
            ("rejected", "Rejected"),
        ],
        default="draft",
    )
    note = fields.Text()
    transfer_id = fields.Many2one(
        "stock.picking", readonly=True,
        help="Created internal transfer when approved.",
    )

    @api.depends("product_id", "source_location_id", "dest_location_id")
    def _compute_name(self):
        for r in self:
            r.name = (
                f"{r.product_id.default_code or '?'}: "
                f"{r.source_location_id.name or '?'} → "
                f"{r.dest_location_id.name or '?'}"
            )

    def action_approve(self):
        for r in self:
            if r.state != "draft":
                continue
            # Create internal transfer
            picking_type = self.env["stock.picking.type"].search([
                ("code", "=", "internal"),
            ], limit=1)
            if picking_type:
                p = self.env["stock.picking"].create({
                    "picking_type_id": picking_type.id,
                    "location_id": r.source_location_id.id,
                    "location_dest_id": r.dest_location_id.id,
                    "origin": f"REBAL/{r.id}",
                    "move_ids": [(0, 0, {
                        "name": r.product_id.display_name,
                        "product_id": r.product_id.id,
                        "product_uom_qty": r.qty_proposed,
                        "product_uom": r.product_id.uom_id.id,
                        "location_id": r.source_location_id.id,
                        "location_dest_id": r.dest_location_id.id,
                    })],
                })
                r.transfer_id = p.id
                r.state = "approved"

    def action_reject(self):
        for r in self:
            r.state = "rejected"
