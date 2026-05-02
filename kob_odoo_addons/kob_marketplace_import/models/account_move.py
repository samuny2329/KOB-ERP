# -*- coding: utf-8 -*-
"""account.move (Customer Invoice / Vendor Bill) extensions to mirror
UAT's invoice layout (Order Type, Delivery Date, Source/Shop, Marketing,
plus Brand on each invoice line).
"""

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── Pulled forward from the originating sale.order ──
    sale_order_type_id = fields.Many2one(
        "sale.order.type",
        string="Order Type",
        compute="_compute_kob_sale_fields",
        store=True,
        index=True,
    )
    x_kob_delivery_date = fields.Date(
        string="Delivery Date",
        compute="_compute_kob_sale_fields",
        store=True,
    )
    x_kob_order_id = fields.Char(
        string="Order ID",
        compute="_compute_kob_sale_fields",
        store=True,
        index=True,
        help="Internal SO reference (KOBSO… or marketplace order_sn).",
    )
    source_id = fields.Many2one(
        "utm.source",
        string="Source",
        compute="_compute_kob_sale_fields",
        store=True,
        readonly=False,
    )
    medium_id = fields.Many2one(
        "utm.medium",
        string="Medium",
        compute="_compute_kob_sale_fields",
        store=True,
        readonly=False,
    )
    campaign_id = fields.Many2one(
        "utm.campaign",
        string="Campaign",
        compute="_compute_kob_sale_fields",
        store=True,
        readonly=False,
    )

    # Cash-flow forecasting fields used by KOB finance team
    x_kob_cash_flow_tags = fields.Many2many(
        "account.account.tag",
        string="Cash Flow Tags",
        domain=[("applicability", "=", "accounts")],
        help="Tag bucket for cash flow forecasting "
             "(e.g. 'Inflow / Sales', 'Outflow / COGS').",
    )
    x_kob_cash_flow_date = fields.Date(
        string="Cash Flow Date",
        help="Expected actual cash-in / cash-out date for forecasting; "
             "may differ from invoice_date_due.",
    )

    @api.depends("invoice_origin", "line_ids.sale_line_ids.order_id")
    def _compute_kob_sale_fields(self):
        SO = self.env["sale.order"]
        for move in self:
            so = False
            # 1. Try sale.order.line backlink
            for line in move.line_ids:
                if line.sale_line_ids:
                    so = line.sale_line_ids[0].order_id
                    break
            # 2. Fallback to invoice_origin → match SO.name
            if not so and move.invoice_origin:
                so = SO.search(
                    [("name", "=", move.invoice_origin)], limit=1,
                ) or SO.search(
                    [("client_order_ref", "=", move.invoice_origin)],
                    limit=1,
                )
            move.sale_order_type_id = so.sale_order_type_id if so else False
            move.x_kob_delivery_date = (
                so.commitment_date if so else False
            )
            move.x_kob_order_id = (
                so.name if so else (move.invoice_origin or False)
            )
            move.source_id = so.source_id if so else False
            move.medium_id = so.medium_id if so else False
            move.campaign_id = so.campaign_id if so else False


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    x_kob_brand = fields.Char(
        string="Brand",
        related="product_id.x_kob_brand",
        store=True,
        readonly=True,
    )
