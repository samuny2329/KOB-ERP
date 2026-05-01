# -*- coding: utf-8 -*-
"""Per-(company, document type) approval routing matrix."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


DOC_TYPES = [
    ("purchase_order", "Purchase Order"),
    ("sale_order", "Sale Order"),
    ("expense", "Expense Report"),
    ("payment", "Vendor Payment"),
    ("journal_entry", "Journal Entry"),
    ("manufacturing_order", "Manufacturing Order"),
]


class KobApprovalMatrix(models.Model):
    _name = "kob.approval.matrix"
    _description = "Approval Matrix"
    _order = "company_id, document_type"
    _sql_constraints = [
        (
            "uniq_company_doctype",
            "unique(company_id, document_type)",
            "Approval matrix already defined for this company / doc type.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    document_type = fields.Selection(DOC_TYPES, required=True)
    name = fields.Char(compute="_compute_name", store=True)
    rule_ids = fields.One2many("kob.approval.matrix.rule", "matrix_id")
    active = fields.Boolean(default=True)

    @api.depends("company_id", "document_type")
    def _compute_name(self):
        for m in self:
            m.name = "%s — %s" % (
                m.company_id.name or "",
                dict(DOC_TYPES).get(m.document_type) or "",
            )

    def lookup(self, amount):
        """Return the rule that matches this amount, or empty recordset."""
        self.ensure_one()
        for rule in self.rule_ids.sorted("threshold_min"):
            if rule.threshold_min <= amount and (
                rule.threshold_max == 0 or amount <= rule.threshold_max
            ):
                return rule
        return self.env["kob.approval.matrix.rule"]


class KobApprovalMatrixRule(models.Model):
    _name = "kob.approval.matrix.rule"
    _description = "Approval Matrix Rule"
    _order = "matrix_id, threshold_min"

    matrix_id = fields.Many2one(
        "kob.approval.matrix", required=True, ondelete="cascade",
    )
    threshold_min = fields.Monetary(currency_field="currency_id")
    threshold_max = fields.Monetary(
        currency_field="currency_id",
        help="0 = no upper limit.",
    )
    approver_user_id = fields.Many2one("res.users")
    approver_group_id = fields.Many2one("res.groups")
    require_unanimous = fields.Boolean(default=False)
    note = fields.Char()
    currency_id = fields.Many2one(
        related="matrix_id.currency_id", store=True, readonly=True,
    )
