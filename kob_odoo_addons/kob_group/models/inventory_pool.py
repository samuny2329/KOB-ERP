# -*- coding: utf-8 -*-
"""Cross-company inventory pooling."""

from odoo import api, fields, models


class KobInventoryPool(models.Model):
    _name = "kob.inventory.pool"
    _description = "Cross-Company Inventory Pool"
    _order = "code"
    _sql_constraints = [("uniq_code", "unique(code)", "Pool code must be unique.")]

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    parent_company_id = fields.Many2one(
        "res.company", string="Parent Company",
        help="Group parent — typically the holding entity.",
    )
    note = fields.Text()
    active = fields.Boolean(default=True)
    member_ids = fields.One2many("kob.inventory.pool.member", "pool_id")
    rule_ids = fields.One2many("kob.inventory.pool.rule", "pool_id")


class KobInventoryPoolMember(models.Model):
    _name = "kob.inventory.pool.member"
    _description = "Inventory Pool Member"
    _sql_constraints = [
        (
            "uniq_pool_warehouse",
            "unique(pool_id, warehouse_id)",
            "Warehouse already a member of this pool.",
        ),
    ]

    pool_id = fields.Many2one(
        "kob.inventory.pool", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    warehouse_id = fields.Many2one(
        "stock.warehouse", required=True, ondelete="restrict",
    )
    priority = fields.Integer(default=10)
    transfer_cost_per_km = fields.Float(digits=(8, 4))


class KobInventoryPoolRule(models.Model):
    _name = "kob.inventory.pool.rule"
    _description = "Inventory Pool Routing Rule"
    _order = "sequence"

    pool_id = fields.Many2one(
        "kob.inventory.pool", required=True, ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    product_category_id = fields.Many2one("product.category")
    strategy = fields.Selection(
        [
            ("priority", "Member priority"),
            ("lowest_cost", "Lowest transfer cost"),
            ("nearest", "Nearest warehouse"),
            ("balance_load", "Balance load"),
        ],
        default="priority",
        required=True,
    )
    min_qty_threshold = fields.Float(digits=(14, 4))
    note = fields.Char()
    active = fields.Boolean(default=True)
