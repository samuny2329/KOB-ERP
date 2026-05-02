# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "kob.dms.mixin"]

    @property
    def _dms_parent_folder(self):
        # Sale-side moves go to Customers, purchase-side to Vendors,
        # everything else to Operations.
        # NOTE: this is read at view-time per record; OK because mixin
        # methods invoke it via getattr.
        if self.move_type in ("out_invoice", "out_refund", "out_receipt"):
            return "Customers"
        if self.move_type in ("in_invoice", "in_refund", "in_receipt"):
            return "Vendors"
        return "Operations"

    def _get_dms_label(self):
        self.ensure_one()
        return self.name or f"MOVE-{self.id}"
