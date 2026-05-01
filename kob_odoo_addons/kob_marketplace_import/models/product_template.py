# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_kob_brand = fields.Char(
        string="KOB Brand",
        help="Brand label used by Print_Label-App for picking sort and "
             "AWB grouping (e.g. KISS-MY-BODY, SKINOXY, DAENG-GI-MEO-RI).",
        index=True,
    )
    x_kob_sku_code = fields.Char(
        string="KOB SKU Code",
        help="Short SKU code printed inside [brackets] at the start of "
             "the product display name (e.g. KHKB038, DUT300).  Used by "
             "the label custom regex.",
        index=True,
    )
