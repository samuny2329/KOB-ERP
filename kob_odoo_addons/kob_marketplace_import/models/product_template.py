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
    # === UAT-parity fields shown on General Information tab ===
    x_kob_wht_tax_id = fields.Many2one(
        "account.tax",
        string="Withholding Tax",
        domain="[('type_tax_use','=','sale'),('amount','<=',0)]",
        help="Default WHT tax applied when this product is invoiced "
             "to a corporate customer (PND 3 / 53 reverse-tagged).",
    )
    x_kob_start_selling_date = fields.Date(
        string="Start Selling Date",
        help="Earliest date this product may be quoted/sold.  Quotes "
             "before this date are blocked at confirmation.",
    )
    x_kob_variant_sales_description = fields.Text(
        string="Variant Sales Description",
        translate=True,
        help="Customer-facing tagline shown on quotation/invoice lines "
             "(e.g. 'Smooth chocolate notes, low acidity').",
    )
    x_kob_internal_note = fields.Text(
        string="Internal Notes",
        help="Free-form internal notes — never shown to customers.",
    )
