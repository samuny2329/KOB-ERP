# -*- coding: utf-8 -*-
"""Company compliance item — regulatory deadline tracker."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobComplianceItem(models.Model):
    _name = "kob.compliance.item"
    _description = "Company Compliance Item"
    _order = "due_date asc"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    item_type = fields.Selection(
        [
            ("dbd", "DBD filing"),
            ("rd", "Revenue Department"),
            ("sso", "Social Security"),
            ("license", "Business License"),
            ("audit", "Annual Audit"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    period_year = fields.Integer()
    due_date = fields.Date(required=True, index=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In progress"),
            ("submitted", "Submitted"),
            ("overdue", "Overdue"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
    )
    submitted_at = fields.Datetime(readonly=True)
    submitted_by = fields.Many2one("res.users", readonly=True)
    rd_receipt_number = fields.Char()
    note = fields.Text()

    def action_start(self):
        for rec in self:
            if rec.state != "pending":
                raise UserError(_("Only pending items can be started."))
            rec.state = "in_progress"

    def action_submit(self):
        for rec in self:
            if rec.state not in ("pending", "in_progress", "overdue"):
                raise UserError(_("Cannot submit from state %s.") % rec.state)
            rec.write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
                "submitted_by": self.env.user.id,
            })

    def action_cancel(self):
        for rec in self:
            if rec.state == "submitted":
                raise UserError(_("Cannot cancel a submitted item."))
            rec.state = "cancelled"

    @api.model
    def _cron_flag_overdue(self):
        """Daily — flip pending/in_progress items past due to overdue."""
        today = fields.Date.context_today(self)
        items = self.search([
            ("state", "in", ("pending", "in_progress")),
            ("due_date", "<", today),
        ])
        items.write({"state": "overdue"})
