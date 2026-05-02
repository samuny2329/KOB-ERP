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
        # wms.sales.order does NOT have date_done — use packed_at / shipped_at
        for rec in self:
            if not rec.date or not rec.kob_user_id:
                rec.activity_log_count = 0
                rec.sales_order_count = 0
                continue
            next_day = fields.Date.add(rec.date, days=1)
            rec.activity_log_count = self.env["wms.activity.log"].search_count([
                ("kob_user_id", "=", rec.kob_user_id.id),
                ("create_date", ">=", rec.date),
                ("create_date", "<", next_day),
            ])
            so_model = self.env["wms.sales.order"]
            # Pick a date field that exists (Odoo 19 / KOB schema may differ)
            date_field = None
            for cand in ("packed_at", "shipped_at", "picked_at", "create_date"):
                if cand in so_model._fields:
                    date_field = cand
                    break
            if date_field:
                rec.sales_order_count = so_model.search_count([
                    (date_field, ">=", rec.date),
                    (date_field, "<", next_day),
                ])
            else:
                rec.sales_order_count = 0

    def action_view_activity_log(self):
        self.ensure_one()
        next_day = fields.Date.add(self.date, days=1)
        return {
            "type": "ir.actions.act_window",
            "name": f"Activity Log — {self.kob_user_id.display_name} {self.date}",
            "res_model": "wms.activity.log",
            "view_mode": "list,form",
            "domain": [
                ("kob_user_id", "=", self.kob_user_id.id),
                ("create_date", ">=", self.date),
                ("create_date", "<", next_day),
            ],
            "context": {
                "default_kob_user_id": self.kob_user_id.id,
                "search_default_groupby_action": 1,
            },
        }

    def action_view_sales_orders(self):
        self.ensure_one()
        so_model = self.env["wms.sales.order"]
        date_field = None
        for cand in ("packed_at", "shipped_at", "picked_at", "create_date"):
            if cand in so_model._fields:
                date_field = cand
                break
        next_day = fields.Date.add(self.date, days=1)
        domain = [
            (date_field or "create_date", ">=", self.date),
            (date_field or "create_date", "<", next_day),
        ]
        return {
            "type": "ir.actions.act_window",
            "name": f"Orders — {self.kob_user_id.display_name} {self.date}",
            "res_model": "wms.sales.order",
            "view_mode": "list,form",
            "domain": domain,
        }
