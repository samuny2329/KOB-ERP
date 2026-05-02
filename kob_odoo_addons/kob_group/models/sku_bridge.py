# -*- coding: utf-8 -*-
"""SKU bridge — master SKU mapped to per-company local product codes."""

from odoo import api, fields, models, _


class KobSkuBridge(models.Model):
    _name = "kob.sku.bridge"
    _description = "Master SKU Bridge"
    _order = "master_sku"
    _sql_constraints = [
        (
            "uniq_master",
            "unique(master_sku)",
            "Master SKU already exists.",
        ),
    ]

    master_sku = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    description = fields.Text()
    member_ids = fields.One2many("kob.sku.bridge.member", "bridge_id")
    active = fields.Boolean(default=True)


class KobSkuBridgeMember(models.Model):
    _name = "kob.sku.bridge.member"
    _description = "SKU Bridge Member"
    _sql_constraints = [
        (
            "uniq_bridge_company",
            "unique(bridge_id, company_id)",
            "Already a mapping for this company in this bridge.",
        ),
        (
            "uniq_bridge_local_sku",
            "unique(bridge_id, local_sku)",
            "Local SKU already used in this bridge.",
        ),
    ]

    bridge_id = fields.Many2one(
        "kob.sku.bridge", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    local_sku = fields.Char(string="Local SKU", required=True)
    local_product_id = fields.Many2one("product.product")
    note = fields.Char()

    @api.model
    def resolve(self, company, master_sku=None, local_sku=None,
                local_product=None):
        """Find a mapping by any of master_sku / local_sku / local_product."""
        domain = [("company_id", "=", company.id)]
        if master_sku:
            domain.append(("bridge_id.master_sku", "=", master_sku))
        if local_sku:
            domain.append(("local_sku", "=", local_sku))
        if local_product:
            domain.append(("local_product_id", "=", local_product.id))
        if len(domain) == 1:
            return self.browse()
        return self.search(domain, limit=1)
