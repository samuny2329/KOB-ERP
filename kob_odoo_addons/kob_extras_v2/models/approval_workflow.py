# -*- coding: utf-8 -*-
"""Phase 29 — Multi-step approval workflow.

Models:
  - kob.approval.request : a generic approval ticket
  - kob.approval.step    : one step in the workflow chain
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobApprovalRequest(models.Model):
    _name = "kob.approval.request"
    _description = "Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Subject", required=True, tracking=True)
    request_type = fields.Selection(
        [
            ("po_approval", "PO Approval"),
            ("budget_increase", "Budget Increase"),
            ("expense_reimburse", "Expense Reimbursement"),
            ("leave_request", "Leave Request"),
            ("price_override", "Price Override"),
            ("contract_termination", "Contract Termination"),
            ("other", "Other"),
        ],
        default="other", required=True,
    )
    requester_id = fields.Many2one(
        "res.users", required=True, default=lambda s: s.env.user,
    )
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id,
    )
    description = fields.Html()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    step_ids = fields.One2many("kob.approval.step", "request_id")
    current_step = fields.Integer(default=0)

    def action_submit(self):
        for r in self:
            if r.state != "draft":
                raise UserError(_("Only draft can be submitted."))
            if not r.step_ids:
                # auto-create default 2-step chain: Manager → Director
                env = self.env
                approvers = env["res.users"].search(
                    [("login", "in", ("admin", "manager", "director"))],
                    limit=2,
                )
                seq = 1
                for u in approvers:
                    env["kob.approval.step"].create({
                        "request_id": r.id,
                        "approver_id": u.id,
                        "sequence": seq,
                        "state": "pending" if seq == 1 else "waiting",
                    })
                    seq += 1
            r.state = "pending"
            r.current_step = 1


class KobApprovalStep(models.Model):
    _name = "kob.approval.step"
    _description = "Approval Step"
    _order = "request_id, sequence"

    request_id = fields.Many2one("kob.approval.request", ondelete="cascade")
    sequence = fields.Integer(default=10)
    approver_id = fields.Many2one("res.users", required=True)
    state = fields.Selection(
        [
            ("waiting", "Waiting Previous"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="waiting",
    )
    decided_at = fields.Datetime(readonly=True)
    note = fields.Char()

    def action_approve(self):
        for s in self:
            s.state = "approved"
            s.decided_at = fields.Datetime.now()
            # Advance to next step
            next_step = s.request_id.step_ids.filtered(
                lambda x: x.sequence > s.sequence and x.state == "waiting"
            )[:1]
            if next_step:
                next_step.state = "pending"
                s.request_id.current_step = next_step.sequence
            else:
                s.request_id.state = "approved"

    def action_reject(self):
        for s in self:
            s.state = "rejected"
            s.decided_at = fields.Datetime.now()
            s.request_id.state = "rejected"
