# -*- coding: utf-8 -*-
"""Production shift — explicit morning/afternoon/night model."""

from odoo import fields, models


class MfgProductionShift(models.Model):
    _name = "mfg.production.shift"
    _description = "Production Shift"
    _order = "warehouse_id, code"
    _sql_constraints = [
        (
            "uniq_warehouse_code",
            "unique(warehouse_id, code)",
            "Shift code must be unique per warehouse.",
        ),
    ]

    warehouse_id = fields.Many2one(
        "stock.warehouse", required=True, ondelete="cascade",
    )
    code = fields.Char(size=10, required=True, help="D / A / N / etc.")
    name = fields.Char(size=60, required=True)
    start_hour = fields.Integer(default=8)
    end_hour = fields.Integer(default=17)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
