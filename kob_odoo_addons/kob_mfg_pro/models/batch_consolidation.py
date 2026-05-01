# -*- coding: utf-8 -*-
"""Batch consolidation — merge multiple draft MOs for the same product."""

from datetime import timedelta

from odoo import api, fields, models, _


class MfgBatchConsolidation(models.Model):
    _name = "mfg.batch.consolidation"
    _description = "MO Batch Consolidation Proposal"
    _order = "proposed_at desc"

    product_id = fields.Many2one(
        "product.product", required=True, ondelete="cascade",
    )
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
    )
    total_mos = fields.Integer(readonly=True)
    total_qty = fields.Float(digits=(14, 4), readonly=True)
    setup_saving_minutes = fields.Integer(readonly=True)
    window_days = fields.Integer(default=3)
    proposed_at = fields.Datetime(default=fields.Datetime.now)
    reviewed_at = fields.Datetime(readonly=True)
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    item_ids = fields.One2many(
        "mfg.batch.consolidation.item", "batch_id",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    def action_accept(self):
        for b in self:
            b.write({
                "status": "accepted",
                "reviewed_at": fields.Datetime.now(),
                "reviewed_by_id": self.env.user.id,
            })

    def action_reject(self):
        for b in self:
            b.write({
                "status": "rejected",
                "reviewed_at": fields.Datetime.now(),
                "reviewed_by_id": self.env.user.id,
            })

    @api.model
    def propose(self, product, window_days=3, setup_minutes=30):
        """Find draft MOs in window for product — propose if ≥2 found."""
        cutoff = fields.Datetime.now() - timedelta(days=window_days)
        MOs = self.env["mrp.production"].search([
            ("product_id", "=", product.id),
            ("state", "=", "draft"),
            ("create_date", ">=", cutoff),
        ])
        if len(MOs) < 2:
            return False
        return self.create({
            "product_id": product.id,
            "total_mos": len(MOs),
            "total_qty": sum(MOs.mapped("product_qty")),
            "setup_saving_minutes": setup_minutes * (len(MOs) - 1),
            "window_days": window_days,
            "item_ids": [(0, 0, {"mo_id": mo.id}) for mo in MOs],
        })


class MfgBatchConsolidationItem(models.Model):
    _name = "mfg.batch.consolidation.item"
    _description = "MO Batch Consolidation Item"

    batch_id = fields.Many2one(
        "mfg.batch.consolidation", required=True, ondelete="cascade",
    )
    mo_id = fields.Many2one("mrp.production", required=True, ondelete="cascade")
