# -*- coding: utf-8 -*-
"""Production signal — sales velocity proposes new MOs."""

from datetime import timedelta

from odoo import api, fields, models, _


class MfgProductionSignal(models.Model):
    _name = "mfg.production.signal"
    _description = "Production Signal"
    _order = "computed_at desc"

    product_id = fields.Many2one(
        "product.product", required=True, ondelete="cascade", index=True,
    )
    bom_id = fields.Many2one("mrp.bom", ondelete="set null")
    platform = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("all", "All"),
        ],
        default="all",
    )
    avg_daily_demand = fields.Float(digits=(14, 4))
    lead_time_days = fields.Integer(default=3)
    current_stock = fields.Float(digits=(14, 4))
    wip_qty = fields.Float(digits=(14, 4))
    suggested_qty = fields.Float(digits=(14, 4))
    computed_at = fields.Datetime(default=fields.Datetime.now)
    status = fields.Selection(
        [
            ("open", "Open"),
            ("converted", "Converted to MO"),
            ("ignored", "Ignored"),
        ],
        default="open",
        required=True,
    )
    converted_mo_id = fields.Many2one(
        "mrp.production", ondelete="set null", readonly=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    def action_convert_to_mo(self):
        """Create a draft mrp.production from this signal."""
        for sig in self:
            if sig.status != "open":
                continue
            bom = sig.bom_id or self.env["mrp.bom"]._bom_find(
                products=sig.product_id,
            ).get(sig.product_id)
            if not bom:
                continue
            mo = self.env["mrp.production"].create({
                "product_id": sig.product_id.id,
                "product_qty": sig.suggested_qty or 0.0,
                "product_uom_id": sig.product_id.uom_id.id,
                "bom_id": bom.id,
                "company_id": sig.company_id.id,
            })
            sig.write({"status": "converted", "converted_mo_id": mo.id})

    def action_ignore(self):
        self.write({"status": "ignored"})

    @api.model
    def create_from_demand(self, product, current_stock=None,
                           wip_qty=None, lookback_days=30,
                           safety_multiplier=1.5):
        """Compute one signal row from sale.order.line history."""
        cutoff = fields.Datetime.now() - timedelta(days=lookback_days)
        SoLine = self.env["sale.order.line"]
        lines = SoLine.search([
            ("product_id", "=", product.id),
            ("order_id.date_order", ">=", cutoff),
            ("order_id.state", "in", ("sale", "done")),
        ])
        total_qty = sum(lines.mapped("product_uom_qty"))
        avg_daily = total_qty / lookback_days if lookback_days else 0.0

        if current_stock is None:
            current_stock = float(product.qty_available or 0)
        if wip_qty is None:
            wip_qty = float(
                self.env["mrp.production"].search([
                    ("product_id", "=", product.id),
                    ("state", "in", ("confirmed", "progress")),
                ]).mapped("product_qty") or [0.0],
            ) and sum(self.env["mrp.production"].search([
                ("product_id", "=", product.id),
                ("state", "in", ("confirmed", "progress")),
            ]).mapped("product_qty")) or 0.0

        # Suggested = avg_daily × (lead + safety) − current − wip
        suggested = max(
            0.0,
            avg_daily * 3 * safety_multiplier - current_stock - wip_qty,
        )
        bom = self.env["mrp.bom"]._bom_find(products=product).get(product)
        return self.create({
            "product_id": product.id,
            "bom_id": bom.id if bom else False,
            "avg_daily_demand": round(avg_daily, 4),
            "lead_time_days": 3,
            "current_stock": round(current_stock, 4),
            "wip_qty": round(wip_qty, 4),
            "suggested_qty": round(suggested, 4),
        })
