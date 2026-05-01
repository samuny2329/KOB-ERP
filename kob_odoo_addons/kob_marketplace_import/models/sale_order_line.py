# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_kob_brand = fields.Char(
        string="KOB Brand",
        related="product_id.x_kob_brand",
        store=True,
        index=True,
    )

    def _prepare_procurement_values(self, *args, **kwargs):
        # Propagate the brand onto the resulting stock.move so the
        # Print_Label-App can read it without joining back to product.
        values = super()._prepare_procurement_values(*args, **kwargs)
        if self.x_kob_brand:
            values["x_kob_brand"] = self.x_kob_brand
        return values
