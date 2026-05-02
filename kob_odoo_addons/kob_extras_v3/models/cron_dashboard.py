# -*- coding: utf-8 -*-
"""Phase 37 — Cron job dashboard.

Wraps ir.cron with KOB-friendly view:
  - last run, next run, success/failure counts
  - one-click 'Run Now' button
"""
from odoo import api, fields, models


class IrCron(models.Model):
    _inherit = "ir.cron"

    last_run_status = fields.Selection(
        [("success", "Success"), ("failed", "Failed"), ("never", "Never Run")],
        compute="_compute_last_run_status",
        store=False,
        string="Last Run Status",
    )

    @api.depends("lastcall", "failure_count")
    def _compute_last_run_status(self):
        for c in self:
            if not c.lastcall:
                c.last_run_status = "never"
            elif c.failure_count > 0:
                c.last_run_status = "failed"
            else:
                c.last_run_status = "success"

    def action_run_now(self):
        for c in self:
            c.method_direct_trigger()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Cron Triggered",
                "message": f"Manually triggered: {', '.join(self.mapped('cron_name'))}",
                "sticky": False,
                "type": "success",
            },
        }
