# -*- coding: utf-8 -*-
"""Approval substitution — fallback approver when primary is on leave."""

from odoo import api, fields, models, _


class KobApprovalSubstitution(models.Model):
    _name = "kob.approval.substitution"
    _description = "Approval Substitution"
    _order = "primary_user_id, effective_from desc"

    primary_user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade",
        string="Primary Approver",
    )
    substitute_user_id = fields.Many2one(
        "res.users", required=True,
        string="Substitute",
    )
    effective_from = fields.Date(required=True)
    effective_to = fields.Date(required=True)
    document_type = fields.Char(
        help="Optional — limits the substitution to one doc type.",
    )
    reason = fields.Char()
    active = fields.Boolean(default=True)

    @api.model
    def resolve_approver(self, user, on_date=None, document_type=None):
        """Return the effective approver — substitute if active, else user."""
        on_date = on_date or fields.Date.context_today(self)
        domain = [
            ("primary_user_id", "=", user.id),
            ("active", "=", True),
            ("effective_from", "<=", on_date),
            ("effective_to", ">=", on_date),
        ]
        if document_type:
            domain.extend([
                "|", ("document_type", "=", document_type),
                ("document_type", "=", False),
            ])
        sub = self.search(domain, order="effective_from desc", limit=1)
        return sub.substitute_user_id if sub else user
