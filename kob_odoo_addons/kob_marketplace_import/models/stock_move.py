# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    x_kob_brand = fields.Char(
        string="KOB Brand",
        index=True,
        help="Copied from the originating sale.order.line at procurement; "
             "Print_Label-App reads this field to sort moves by brand.",
    )
