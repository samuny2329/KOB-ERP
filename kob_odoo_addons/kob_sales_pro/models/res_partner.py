# -*- coding: utf-8 -*-
"""Customer extensions: LTV score, blocked flag, customer group."""

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ltv_score = fields.Float(
        digits=(14, 2),
        readonly=True,
        help="Rolling 90-day LTV score from kob.customer.ltv.snapshot.",
    )
    customer_group = fields.Selection(
        [
            ("vip", "VIP"),
            ("regular", "Regular"),
            ("wholesale", "Wholesale"),
            ("retail", "Retail"),
        ],
    )
    blocked = fields.Boolean(
        help="Block this customer from confirming new SOs (credit hold, "
             "fraud, etc).",
    )
    blocked_reason = fields.Char()
    ltv_snapshot_ids = fields.One2many(
        "kob.customer.ltv.snapshot", "partner_id",
        string="LTV Snapshots",
    )
