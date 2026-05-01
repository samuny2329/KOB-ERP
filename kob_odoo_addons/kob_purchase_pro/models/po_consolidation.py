# -*- coding: utf-8 -*-
"""PO consolidation proposal — merge same-vendor draft POs in a window."""

from datetime import timedelta

from odoo import api, fields, models, _


class KobPoConsolidationProposal(models.Model):
    _name = "kob.po.consolidation.proposal"
    _description = "PO Consolidation Proposal"
    _order = "proposed_at desc"

    vendor_id = fields.Many2one(
        "res.partner", required=True, ondelete="cascade",
        domain=[("supplier_rank", ">", 0)],
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    status = fields.Selection(
        [
            ("pending", "Pending review"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    total_lines = fields.Integer(readonly=True)
    original_total = fields.Monetary(currency_field="currency_id", readonly=True)
    estimated_saving = fields.Monetary(
        currency_field="currency_id", readonly=True,
    )
    saving_pct = fields.Float(digits=(5, 2), readonly=True)
    window_days = fields.Integer(default=7)
    proposed_at = fields.Datetime(default=fields.Datetime.now)
    reviewed_at = fields.Datetime(readonly=True)
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    item_ids = fields.One2many(
        "kob.po.consolidation.item", "proposal_id", string="Items",
    )

    def action_accept(self):
        for p in self:
            p.write({
                "status": "accepted",
                "reviewed_at": fields.Datetime.now(),
                "reviewed_by_id": self.env.user.id,
            })

    def action_reject(self):
        for p in self:
            p.write({
                "status": "rejected",
                "reviewed_at": fields.Datetime.now(),
                "reviewed_by_id": self.env.user.id,
            })

    @api.model
    def propose(self, vendor, window_days=7):
        """Find draft POs for vendor in window — proposal if ≥2 found."""
        cutoff = fields.Datetime.now() - timedelta(days=window_days)
        POs = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id),
            ("state", "=", "draft"),
            ("date_order", ">=", cutoff),
        ])
        if len(POs) < 2:
            return False
        original_total = sum(POs.mapped("amount_total"))
        # Heuristic: 3% saving from volume tier
        saving = round(original_total * 0.03, 2)
        prop = self.create({
            "vendor_id": vendor.id,
            "total_lines": len(POs),
            "original_total": original_total,
            "estimated_saving": saving,
            "saving_pct": 3.0,
            "window_days": window_days,
            "item_ids": [(0, 0, {"purchase_order_id": po.id}) for po in POs],
        })
        return prop


class KobPoConsolidationItem(models.Model):
    _name = "kob.po.consolidation.item"
    _description = "PO Consolidation Item"

    proposal_id = fields.Many2one(
        "kob.po.consolidation.proposal", required=True, ondelete="cascade",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", required=True, ondelete="cascade",
    )
