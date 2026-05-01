# -*- coding: utf-8 -*-
"""mrp.workcenter — add OEE target + KOB warehouse link."""

from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    oee_target = fields.Float(
        digits=(5, 2), default=85.0,
        help="Target OEE % above which the work-centre is considered healthy.",
    )
    kob_warehouse_id = fields.Many2one(
        "stock.warehouse",
        help="Maps the WMS warehouse this work-centre physically lives in.",
    )
