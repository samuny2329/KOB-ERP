# -*- coding: utf-8 -*-
"""Order Type — mirrors UAT's ``sale.order.type`` (community sale_order_type
addon).  Captured from kissgroupdatacenter.com; values:
  Return Order / Sampling Order / Normal Order / Consignment Order /
  Direct Return Order / Adj Inventory / Assets.
Marketplace imports default to "Normal Order".
"""

from odoo import api, fields, models


class SaleOrderType(models.Model):
    _name = "sale.order.type"
    _description = "Sale Order Type"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        help="Leave empty for shared (all companies see this type).",
    )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_order_type_id = fields.Many2one(
        "sale.order.type",
        string="Order Type",
        ondelete="restrict",
        index=True,
        help="Mirrors UAT's Order Type field.  Defaults to 'Normal "
             "Order' for marketplace imports.",
    )
    sale_order_type_name = fields.Char(
        related="sale_order_type_id.name", store=True, readonly=True,
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sale_order_type_id = fields.Many2one(
        "sale.order.type",
        string="Order Type",
        compute="_compute_kob_order_type",
        store=True,
        index=True,
    )
    sale_order_type_name = fields.Char(
        related="sale_order_type_id.name", store=True, readonly=True,
    )

    @api.depends("sale_id", "sale_id.sale_order_type_id")
    def _compute_kob_order_type(self):
        for pick in self:
            pick.sale_order_type_id = (
                pick.sale_id.sale_order_type_id
                if pick.sale_id else False
            )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_kob_product_category = fields.Char(
        string="KOB Product Category",
        help="Mirrors UAT's x_kob_product_category char field.",
    )
