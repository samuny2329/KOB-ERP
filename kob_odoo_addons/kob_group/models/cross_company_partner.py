# -*- coding: utf-8 -*-
"""Cross-company customer / vendor profile + per-company links.

A "group" customer can buy from multiple companies in the group; the
per-company partner records remain separate (Odoo res.partner is
company-scoped) but are mirrored to a shared profile so total exposure
and history can be reported group-wide.
"""

from odoo import api, fields, models, _


class KobCrossCustomer(models.Model):
    _name = "kob.cross.customer"
    _description = "Cross-Company Customer Profile"
    _order = "code"
    _sql_constraints = [
        ("uniq_code", "unique(code)", "Customer profile code must be unique."),
    ]

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    tax_id = fields.Char()
    customer_group = fields.Selection(
        [
            ("vip", "VIP"),
            ("regular", "Regular"),
            ("wholesale", "Wholesale"),
            ("retail", "Retail"),
        ],
    )
    group_credit_limit = fields.Monetary(currency_field="currency_id")
    group_credit_consumed = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_credit_consumed",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.company.currency_id,
    )
    link_ids = fields.One2many("kob.cross.customer.link", "profile_id")
    blocked = fields.Boolean()
    blocked_reason = fields.Char()
    active = fields.Boolean(default=True)

    @api.depends("link_ids.partner_id")
    def _compute_credit_consumed(self):
        Move = self.env["account.move"]
        for prof in self:
            partners = prof.link_ids.mapped("partner_id")
            if not partners:
                prof.group_credit_consumed = 0.0
                continue
            # Open AR balance — sum residuals on open customer invoices
            open_invs = Move.search([
                ("partner_id", "in", partners.ids),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
            ])
            prof.group_credit_consumed = sum(
                open_invs.mapped("amount_residual"),
            )


class KobCrossCustomerLink(models.Model):
    _name = "kob.cross.customer.link"
    _description = "Cross-Customer ↔ Per-Co Partner Link"
    _sql_constraints = [
        (
            "uniq_profile_partner",
            "unique(profile_id, partner_id)",
            "Partner already linked to this profile.",
        ),
    ]

    profile_id = fields.Many2one(
        "kob.cross.customer", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    partner_id = fields.Many2one(
        "res.partner", required=True,
        domain=[("customer_rank", ">", 0)],
    )


class KobCrossVendor(models.Model):
    _name = "kob.cross.vendor"
    _description = "Cross-Company Vendor Profile"
    _order = "code"
    _sql_constraints = [
        ("uniq_code", "unique(code)", "Vendor profile code must be unique."),
    ]

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    tax_id = fields.Char()
    wht_type = fields.Selection(
        [("none", "None"), ("pnd3", "PND3"), ("pnd53", "PND53")],
        default="none",
    )
    wht_rate = fields.Float(digits=(6, 4))
    link_ids = fields.One2many("kob.cross.vendor.link", "profile_id")
    active = fields.Boolean(default=True)
    note = fields.Text()


class KobCrossVendorLink(models.Model):
    _name = "kob.cross.vendor.link"
    _description = "Cross-Vendor ↔ Per-Co Partner Link"
    _sql_constraints = [
        (
            "uniq_profile_partner",
            "unique(profile_id, partner_id)",
            "Partner already linked to this profile.",
        ),
    ]

    profile_id = fields.Many2one(
        "kob.cross.vendor", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    partner_id = fields.Many2one(
        "res.partner", required=True,
        domain=[("supplier_rank", ">", 0)],
    )
