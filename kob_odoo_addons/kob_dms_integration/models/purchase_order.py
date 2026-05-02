# -*- coding: utf-8 -*-
from odoo import models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "kob.dms.mixin"]
    _dms_parent_folder = "Vendors"

    def _get_dms_label(self):
        self.ensure_one()
        return self.name or f"PO-{self.id}"
