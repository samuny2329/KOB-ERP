# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Source reference (utm.source.name) — same on the originating SO.
    x_kob_source_ref = fields.Many2one(
        comodel_name="utm.source",
        string="KOB Source Ref",
        index=True,
        help="utm.source of the SO that produced this picking — used by "
             "Print_Label-App to filter Shopee/TikTok/Lazada deliveries.",
    )

    # Order timestamp from marketplace (separate from create_date).
    x_kob_order_date_ref = fields.Datetime(
        string="KOB Order Date Ref",
        index=True,
        help="Timestamp the marketplace placed the order (used for "
             "cutoff filters in Print_Label-App).",
    )

    # Computed availability rolled up from move state.
    x_kob_products_availability = fields.Selection(
        selection=[
            ("Available", "Available"),
            ("Partial", "Partial"),
            ("Out of stock", "Out of stock"),
        ],
        string="KOB Products Availability",
        compute="_compute_x_kob_products_availability",
        store=True,
    )

    x_kob_fake_order = fields.Boolean(
        string="KOB Fake Order",
        index=True,
        help="True if the originating SO carries the 'fake_order' tag.",
    )

    @api.depends("move_ids.state", "move_ids.product_uom_qty",
                 "move_ids.quantity")
    def _compute_x_kob_products_availability(self):
        for picking in self:
            if not picking.move_ids:
                picking.x_kob_products_availability = "Out of stock"
                continue
            done = sum(picking.move_ids.mapped("quantity"))
            demand = sum(picking.move_ids.mapped("product_uom_qty"))
            if done >= demand and demand > 0:
                picking.x_kob_products_availability = "Available"
            elif done > 0:
                picking.x_kob_products_availability = "Partial"
            else:
                # If reservation already covers demand, treat as Available.
                if all(m.state in ("assigned", "done") for m in picking.move_ids):
                    picking.x_kob_products_availability = "Available"
                else:
                    picking.x_kob_products_availability = "Out of stock"

    def _action_done(self):
        # On confirmation, copy x_kob_source_ref + x_kob_order_date_ref
        # + x_kob_fake_order from the originating SO.
        for picking in self:
            if picking.sale_id and not picking.x_kob_source_ref:
                picking.x_kob_source_ref = picking.sale_id.source_id
            if picking.sale_id and not picking.x_kob_order_date_ref:
                picking.x_kob_order_date_ref = picking.sale_id.date_order
            if picking.sale_id:
                fake_tag = self.env.ref(
                    "kob_marketplace_import.tag_fake_order",
                    raise_if_not_found=False,
                )
                if fake_tag:
                    picking.x_kob_fake_order = (
                        fake_tag in picking.sale_id.tag_ids
                    )
        return super()._action_done()
