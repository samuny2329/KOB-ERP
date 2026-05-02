# -*- coding: utf-8 -*-
"""KOB KPI Dashboard — TransientModel showing real-time totals.

Each opening recomputes the metrics. No historic snapshot table needed.
"""
from datetime import date, timedelta
from odoo import api, fields, models


class KobKpiDashboard(models.TransientModel):
    _name = "kob.kpi.dashboard"
    _description = "KOB KPI Tile Dashboard"

    # Sales (last 30 days)
    sales_revenue_30d = fields.Float(compute="_compute_metrics")
    sales_orders_30d = fields.Integer(compute="_compute_metrics")
    sales_avg_30d = fields.Float(compute="_compute_metrics")
    # Purchase (last 30 days)
    purchase_total_30d = fields.Float(compute="_compute_metrics")
    purchase_orders_30d = fields.Integer(compute="_compute_metrics")
    # Inventory
    inventory_value = fields.Float(compute="_compute_metrics")
    inventory_lots = fields.Integer(compute="_compute_metrics")
    # AR / AP
    ar_outstanding = fields.Float(compute="_compute_metrics")
    ap_outstanding = fields.Float(compute="_compute_metrics")
    # Helpdesk
    helpdesk_open = fields.Integer(compute="_compute_metrics")
    helpdesk_urgent = fields.Integer(compute="_compute_metrics")
    # Maintenance
    maintenance_pending = fields.Integer(compute="_compute_metrics")
    # Cycle counts
    cycle_count_due = fields.Integer(compute="_compute_metrics")

    def _compute_metrics(self):
        thirty = fields.Date.today() - timedelta(days=30)
        for r in self:
            # Sales
            sos = self.env["sale.order"].search([
                ("state", "in", ("sale", "done")),
                ("date_order", ">=", thirty),
            ])
            r.sales_revenue_30d = sum(sos.mapped("amount_total"))
            r.sales_orders_30d = len(sos)
            r.sales_avg_30d = (r.sales_revenue_30d / r.sales_orders_30d) \
                              if r.sales_orders_30d else 0.0

            # Purchase
            pos = self.env["purchase.order"].search([
                ("state", "in", ("purchase", "done")),
                ("date_order", ">=", thirty),
            ])
            r.purchase_total_30d = sum(pos.mapped("amount_total"))
            r.purchase_orders_30d = len(pos)

            # Inventory
            self.env.cr.execute(
                "SELECT COALESCE(SUM(quantity), 0)::numeric, COUNT(DISTINCT lot_id) "
                "FROM stock_quant WHERE quantity > 0",
            )
            row = self.env.cr.fetchone()
            r.inventory_value = float(row[0] or 0)
            r.inventory_lots = int(row[1] or 0)

            # AR / AP
            self.env.cr.execute("""
                SELECT
                    COALESCE(SUM(amount_residual_signed) FILTER (
                        WHERE move_type IN ('out_invoice', 'out_receipt')
                    ), 0)::numeric AS ar,
                    COALESCE(SUM(-amount_residual_signed) FILTER (
                        WHERE move_type IN ('in_invoice', 'in_receipt')
                    ), 0)::numeric AS ap
                FROM account_move WHERE state = 'posted'
            """)
            ar, ap = self.env.cr.fetchone()
            r.ar_outstanding = float(ar or 0)
            r.ap_outstanding = float(ap or 0)

            # Helpdesk
            if "kob.helpdesk.ticket" in self.env:
                tickets = self.env["kob.helpdesk.ticket"].search([
                    ("state", "in", ("new", "in_progress", "waiting")),
                ])
                r.helpdesk_open = len(tickets)
                r.helpdesk_urgent = len(tickets.filtered(lambda t: t.priority == "3"))
            else:
                r.helpdesk_open = 0
                r.helpdesk_urgent = 0

            # Maintenance
            if "maintenance.request" in self.env:
                r.maintenance_pending = self.env["maintenance.request"].search_count([
                    ("stage_id.done", "=", False),
                ])
            else:
                r.maintenance_pending = 0

            # Cycle counts
            if "stock.cycle.count" in self.env:
                r.cycle_count_due = self.env["stock.cycle.count"].search_count([
                    ("state", "in", ("draft", "open")),
                ])
            else:
                r.cycle_count_due = 0
