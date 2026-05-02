# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "kob.dms.mixin"]
    _dms_parent_folder = "Customers"

    def _get_dms_label(self):
        self.ensure_one()
        return self.name or f"SO-{self.id}"
