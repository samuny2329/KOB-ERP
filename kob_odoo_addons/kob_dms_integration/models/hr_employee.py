# -*- coding: utf-8 -*-
from odoo import models


class HrEmployee(models.Model):
    _name = "hr.employee"
    _inherit = ["hr.employee", "kob.dms.mixin"]
    _dms_parent_folder = "Employees"

    def _get_dms_label(self):
        self.ensure_one()
        return self.name or f"EMP-{self.id}"
