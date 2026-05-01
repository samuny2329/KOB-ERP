# -*- coding: utf-8 -*-
"""mrp.unbuild — record reason + done-at timestamp on unbuild."""

from odoo import fields, models


class MrpUnbuild(models.Model):
    _inherit = "mrp.unbuild"

    kob_reason = fields.Text(string="KOB Unbuild Reason")
    kob_done_at = fields.Datetime(readonly=True)

    def action_unbuild(self):
        res = super().action_unbuild()
        for u in self:
            u.kob_done_at = fields.Datetime.now()
        return res
