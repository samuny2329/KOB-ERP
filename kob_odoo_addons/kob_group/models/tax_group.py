# -*- coding: utf-8 -*-
"""Tax group — VAT consolidation across companies (Thai RD scheme)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobTaxGroup(models.Model):
    _name = "kob.tax.group"
    _description = "Tax Group"
    _order = "code"
    _sql_constraints = [
        ("uniq_code", "unique(code)", "Tax group code must be unique."),
    ]

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    rd_registration_no = fields.Char(string="RD Registration No.")
    effective_from = fields.Date()
    effective_to = fields.Date()
    active = fields.Boolean(default=True)
    member_ids = fields.One2many("kob.tax.group.member", "tax_group_id")
    note = fields.Text()


class KobTaxGroupMember(models.Model):
    _name = "kob.tax.group.member"
    _description = "Tax Group Member"
    _sql_constraints = [
        (
            "uniq_group_company_window",
            "unique(tax_group_id, company_id, joined_on)",
            "Company already a member from that date.",
        ),
    ]

    tax_group_id = fields.Many2one(
        "kob.tax.group", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    joined_on = fields.Date(required=True, default=fields.Date.context_today)
    left_on = fields.Date()
    is_lead = fields.Boolean(
        help="Lead company that submits the consolidated return.",
    )

    @api.model
    def companies_in_same_group(self, company_a, company_b, on_date=None):
        """Helper — true if A and B share an active tax group on `on_date`."""
        on_date = on_date or fields.Date.context_today(self)
        members = self.search([
            ("company_id", "in", [company_a.id, company_b.id]),
            ("joined_on", "<=", on_date),
            "|", ("left_on", "=", False), ("left_on", ">=", on_date),
        ])
        groups_a = members.filtered(
            lambda m: m.company_id == company_a,
        ).mapped("tax_group_id")
        groups_b = members.filtered(
            lambda m: m.company_id == company_b,
        ).mapped("tax_group_id")
        return bool(groups_a & groups_b)
