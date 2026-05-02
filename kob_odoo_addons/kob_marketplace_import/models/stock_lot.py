# -*- coding: utf-8 -*-
"""Per-lot valuation extensions for stock.lot.

Odoo's standard valuation (stock_account) records cost on the move
but does not break it out per lot.  For cosmetics where each
production batch can have a different actual cost (raw-material
batch, exchange rate at the time of import, etc.) we need to track
cost separately per lot.

This is a *lightweight* implementation — it stores a per-lot unit
cost and a stored computed total value.  The KOB accounting
integration (Phase 5-adv) reads these fields when reconciling
period-end stock value.
"""

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    x_kob_cost_per_unit = fields.Float(
        string="KOB Cost / Unit",
        digits="Product Price",
        help="Unit cost specific to this lot.  Defaults to the "
             "product's standard_price at the time the lot was created "
             "but can be overridden manually.",
    )
    x_kob_on_hand_qty = fields.Float(
        string="On-hand (lot)",
        compute="_compute_kob_lot_value",
        store=False,
        digits="Product Unit of Measure",
    )
    x_kob_total_value = fields.Monetary(
        string="KOB Lot Value",
        compute="_compute_kob_lot_value",
        store=False,
        currency_field="x_kob_currency_id",
    )
    x_kob_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_kob_currency",
        store=False,
    )

    def _compute_kob_currency(self):
        for lot in self:
            lot.x_kob_currency_id = (
                lot.company_id.currency_id
                or self.env.company.currency_id
            )

    @api.depends("x_kob_cost_per_unit", "product_id", "company_id")
    def _compute_kob_lot_value(self):
        Quant = self.env["stock.quant"]
        for lot in self:
            quants = Quant.search([
                ("lot_id", "=", lot.id),
                ("location_id.usage", "=", "internal"),
            ])
            on_hand = sum(quants.mapped("quantity"))
            lot.x_kob_on_hand_qty = on_hand
            lot.x_kob_total_value = on_hand * (lot.x_kob_cost_per_unit or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        # If cost not provided, seed from product.standard_price.
        for vals in vals_list:
            if "x_kob_cost_per_unit" in vals and vals["x_kob_cost_per_unit"]:
                continue
            prod_id = vals.get("product_id")
            if prod_id:
                product = self.env["product.product"].browse(prod_id)
                vals["x_kob_cost_per_unit"] = float(
                    product.standard_price or 0,
                )
        return super().create(vals_list)
