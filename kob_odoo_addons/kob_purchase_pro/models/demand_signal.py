# -*- coding: utf-8 -*-
"""Demand signal — sales velocity → suggested replenishment qty.

Append-only feed.  Each signal proposes a (vendor, qty, price) buy order;
purchasers accept by clicking ``Convert to RFQ``.
"""

from datetime import timedelta

from odoo import api, fields, models, _


class KobDemandSignal(models.Model):
    _name = "kob.demand.signal"
    _description = "Demand Signal"
    _order = "computed_at desc"

    product_id = fields.Many2one(
        "product.product", required=True, ondelete="cascade", index=True,
    )
    vendor_id = fields.Many2one(
        "res.partner", ondelete="set null",
        domain=[("supplier_rank", ">", 0)],
    )
    platform = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("all", "All"),
        ],
        default="all",
    )
    avg_daily_sales = fields.Float(digits=(14, 4))
    lead_time_days = fields.Integer(default=7)
    safety_stock = fields.Float(digits=(14, 4))
    current_on_hand = fields.Float(digits=(14, 4))
    suggested_qty = fields.Float(digits=(14, 4))
    suggested_price = fields.Float(digits=(14, 4))
    computed_at = fields.Datetime(default=fields.Datetime.now)
    status = fields.Selection(
        [
            ("open", "Open"),
            ("converted", "Converted to RFQ"),
            ("ignored", "Ignored"),
        ],
        default="open",
        required=True,
    )
    converted_po_id = fields.Many2one(
        "purchase.order", ondelete="set null",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    def action_convert_to_rfq(self):
        """Spawn a draft purchase.order from this signal."""
        for sig in self:
            if sig.status != "open":
                continue
            if not sig.vendor_id or not sig.product_id:
                continue
            po = self.env["purchase.order"].create({
                "partner_id": sig.vendor_id.id,
                "company_id": sig.company_id.id,
                "order_line": [(0, 0, {
                    "product_id": sig.product_id.id,
                    "name": sig.product_id.display_name,
                    "product_qty": sig.suggested_qty or 0,
                    "price_unit": sig.suggested_price or 0,
                    "product_uom_id": sig.product_id.uom_po_id.id,
                    "date_planned": fields.Datetime.now() + timedelta(
                        days=sig.lead_time_days or 7,
                    ),
                })],
            })
            sig.write({"status": "converted", "converted_po_id": po.id})
        return True

    def action_ignore(self):
        self.write({"status": "ignored"})

    @api.model
    def compute_for_product(self, product, current_on_hand=None,
                            lookback_days=30, safety_multiplier=1.5):
        """Compute one signal row for a product based on recent sales."""
        cutoff = fields.Datetime.now() - timedelta(days=lookback_days)
        SoLine = self.env["sale.order.line"]
        lines = SoLine.search([
            ("product_id", "=", product.id),
            ("order_id.date_order", ">=", cutoff),
            ("order_id.state", "in", ("sale", "done")),
        ])
        total_qty = sum(lines.mapped("product_uom_qty"))
        avg_daily = total_qty / lookback_days if lookback_days else 0

        # Pick best vendor by lowest price
        best = self.env["product.supplierinfo"].search([
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
        ], order="price asc", limit=1)
        vendor = best.partner_id if best else None
        price = float(best.price) if best else 0.0
        lead = (vendor.lead_time_days if vendor else None) or 7

        if current_on_hand is None:
            current_on_hand = float(product.qty_available or 0)

        safety = avg_daily * safety_multiplier
        suggested = max(0.0, avg_daily * lead + safety - current_on_hand)

        return self.create({
            "product_id": product.id,
            "vendor_id": vendor.id if vendor else False,
            "avg_daily_sales": round(avg_daily, 4),
            "lead_time_days": lead,
            "safety_stock": round(safety, 4),
            "current_on_hand": round(current_on_hand, 4),
            "suggested_qty": round(suggested, 4),
            "suggested_price": round(price, 4),
        })
