# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WmsWorkerPerformance(models.Model):
    _inherit = "wms.worker.performance"

    activity_log_count = fields.Integer(
        string="Activity Log Count",
        compute="_compute_activity_counts",
    )
    sales_order_count = fields.Integer(
        string="Sales Order Count",
        compute="_compute_activity_counts",
    )

    @api.depends("kob_user_id", "date")
    def _compute_activity_counts(self):
        for rec in self:
            if not rec.date or not rec.kob_user_id:
                rec.activity_log_count = 0
                rec.sales_order_count = 0
                continue
            rec.activity_log_count = self.env["wms.activity.log"].search_count([
                ("kob_user_id", "=", rec.kob_user_id.id),
                ("create_date", ">=", rec.date),
                ("create_date", "<", fields.Date.add(rec.date, days=1)),
            ])
            so_model = self.env["wms.sales.order"]
            if "picker_id" in so_model._fields or "packer_id" in so_model._fields:
                domain = [("date_done", ">=", rec.date),
                          ("date_done", "<", fields.Date.add(rec.date, days=1))]
                if rec.user_id:
                    if "packer_id" in so_model._fields:
                        domain.append(("packer_id", "=", rec.user_id.id))
                rec.sales_order_count = so_model.search_count(domain)
            else:
                rec.sales_order_count = 0

    def action_view_activity_log(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Activity Log — {self.kob_user_id.display_name} {self.date}",
            "res_model": "wms.activity.log",
            "view_mode": "list,form",
            "domain": [
                ("kob_user_id", "=", self.kob_user_id.id),
                ("create_date", ">=", self.date),
                ("create_date", "<", fields.Date.add(self.date, days=1)),
            ],
            "context": {
                "default_kob_user_id": self.kob_user_id.id,
                "search_default_groupby_action": 1,
            },
        }

    def action_view_sales_orders(self):
        self.ensure_one()
        domain = [
            ("date_done", ">=", self.date),
            ("date_done", "<", fields.Date.add(self.date, days=1)),
        ]
        if self.user_id and "packer_id" in self.env["wms.sales.order"]._fields:
            domain.append(("packer_id", "=", self.user_id.id))
        return {
            "type": "ir.actions.act_window",
            "name": f"Orders — {self.kob_user_id.display_name} {self.date}",
            "res_model": "wms.sales.order",
            "view_mode": "list,form",
            "domain": domain,
        }
