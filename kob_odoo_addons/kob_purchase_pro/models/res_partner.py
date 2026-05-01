# -*- coding: utf-8 -*-
"""Vendor extensions: WHT, lead time, performance score."""

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Withholding-tax defaults applied to POs from this vendor.
    wht_type = fields.Selection(
        [
            ("none", "None"),
            ("pnd3", "PND3 — Individual service"),
            ("pnd53", "PND53 — Corporate"),
        ],
        default="none",
        help="Default withholding form to use when paying this vendor.",
    )
    wht_rate = fields.Float(
        digits=(6, 4),
        default=0,
        help="Common rates: 1 (transport), 2 (advertising), 3 (services), "
             "5 (rent), 10 (dividend), 15 (interest, royalty).",
    )
    lead_time_days = fields.Integer(
        default=7,
        help="Default supplier lead time in days; used by demand signal.",
    )
    performance_score = fields.Float(
        digits=(5, 2),
        readonly=True,
        help="Last computed overall vendor performance score (0..100).",
    )
