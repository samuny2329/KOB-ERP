# -*- coding: utf-8 -*-
"""Rolling vendor performance KPI snapshot.

Composite score = 0.35×on_time + 0.30×fill + 0.25×quality + 0.10×price_stability
"""

import statistics
from datetime import date, timedelta

from odoo import api, fields, models, _


class KobVendorPerformance(models.Model):
    _name = "kob.vendor.performance"
    _description = "Vendor Performance Snapshot"
    _order = "period_year desc, period_month desc, vendor_id"
    _sql_constraints = [
        (
            "uniq_vendor_period",
            "unique(vendor_id, period_year, period_month)",
            "Performance already snapshotted for this vendor / month.",
        ),
    ]

    vendor_id = fields.Many2one(
        "res.partner", required=True, ondelete="cascade",
        domain=[("supplier_rank", ">", 0)],
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    on_time_rate = fields.Float(
        digits=(5, 2),
        help="% of receipts validated on or before expected date.",
    )
    fill_rate = fields.Float(digits=(5, 2))
    quality_rate = fields.Float(digits=(5, 2))
    price_stability = fields.Float(
        digits=(5, 2),
        help="100 = stable; lower as price stdev grows.",
    )
    overall_score = fields.Float(
        digits=(5, 2),
        readonly=True,
    )
    po_count = fields.Integer(readonly=True)
    receipt_count = fields.Integer(readonly=True)
    computed_at = fields.Datetime(readonly=True)

    @api.model
    def recompute(self, vendor, year, month):
        """Recompute KPI for one (vendor, year, month).

        Looks back over a 90-day window ending on the period end.
        """
        if not vendor:
            return self.browse()
        # Window
        end = date(year, month, 28) + timedelta(days=4)
        end = end.replace(day=1) - timedelta(days=1)  # last day of month
        start = end - timedelta(days=90)

        POs = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id),
            ("date_order", ">=", fields.Datetime.to_string(start)),
            ("date_order", "<=", fields.Datetime.to_string(end)),
        ])
        # On-time / quality from receipts
        pickings = self.env["stock.picking"].search([
            ("origin", "in", POs.mapped("name")),
            ("state", "=", "done"),
            ("date_done", "!=", False),
        ])
        receipt_count = len(pickings)
        if pickings:
            on_time = sum(
                1 for p in pickings
                if p.scheduled_date and p.date_done
                and p.date_done <= p.scheduled_date
            )
            on_time_rate = round(on_time / receipt_count * 100.0, 2)
        else:
            on_time_rate = 0.0

        # Fill rate: total received / total ordered across PO lines
        ordered = sum(POs.mapped("order_line.product_qty")) or 0.0
        received = sum(POs.mapped("order_line.qty_received")) or 0.0
        fill_rate = (
            round(min(100.0, (received / ordered) * 100.0), 2)
            if ordered else 0.0
        )

        # Quality: assume 100 unless we have integration with returns
        quality_rate = 100.0

        # Price stability: stdev of unit prices for the same product
        prices_per_product = {}
        for line in POs.mapped("order_line"):
            prices_per_product.setdefault(line.product_id.id, []).append(
                float(line.price_unit or 0),
            )
        instabilities = []
        for prices in prices_per_product.values():
            if len(prices) < 2:
                continue
            mean = statistics.mean(prices)
            if mean <= 0:
                continue
            stdev = statistics.pstdev(prices)
            instabilities.append(min(1.0, stdev / mean))
        if instabilities:
            avg_inst = sum(instabilities) / len(instabilities)
            price_stability = round(max(0.0, (1.0 - avg_inst)) * 100.0, 2)
        else:
            price_stability = 100.0

        overall = round(
            0.35 * on_time_rate
            + 0.30 * fill_rate
            + 0.25 * quality_rate
            + 0.10 * price_stability,
            2,
        )

        existing = self.search([
            ("vendor_id", "=", vendor.id),
            ("period_year", "=", year),
            ("period_month", "=", month),
        ], limit=1)
        vals = {
            "vendor_id": vendor.id,
            "period_year": year,
            "period_month": month,
            "on_time_rate": on_time_rate,
            "fill_rate": fill_rate,
            "quality_rate": quality_rate,
            "price_stability": price_stability,
            "overall_score": overall,
            "po_count": len(POs),
            "receipt_count": receipt_count,
            "computed_at": fields.Datetime.now(),
        }
        if existing:
            existing.write(vals)
            rec = existing
        else:
            rec = self.create(vals)
        vendor.performance_score = overall
        return rec

    @api.model
    def _cron_recompute_current_month(self):
        """Daily cron — refresh all active vendors' current-month snapshot."""
        today = fields.Date.context_today(self)
        vendors = self.env["res.partner"].search([
            ("supplier_rank", ">", 0),
            ("active", "=", True),
        ])
        for v in vendors:
            self.recompute(v, today.year, today.month)
