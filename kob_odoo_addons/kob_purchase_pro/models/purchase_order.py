# -*- coding: utf-8 -*-
"""Purchase Order: approval gating + budget link + KOB notes."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    note_internal = fields.Text(
        string="Internal Note",
        help="Visible to KOB staff only — never exposed on the vendor PDF.",
    )
    note_vendor = fields.Text(
        string="Vendor-facing Note",
        help="Printed on the PO/RFQ sent to the vendor.",
    )
    approval_state = fields.Selection(
        [
            ("not_required", "Not required"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="not_required",
        tracking=True,
    )
    approver_id = fields.Many2one("res.users", string="Approver", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    budget_id = fields.Many2one(
        "kob.procurement.budget",
        string="Procurement Budget",
        ondelete="set null",
    )

    def action_request_approval(self):
        for po in self:
            if po.state not in ("draft", "sent"):
                raise UserError(
                    _("Only draft / sent POs can be sent for approval."),
                )
            po.approval_state = "pending"

    def action_approve(self):
        for po in self:
            if po.approval_state != "pending":
                raise UserError(_("PO is not pending approval."))
            po.write({
                "approval_state": "approved",
                "approver_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })

    def action_reject(self):
        for po in self:
            if po.approval_state != "pending":
                raise UserError(_("PO is not pending approval."))
            po.approval_state = "rejected"

    def button_confirm(self):
        # Budget gate: if a budget is linked, ensure remaining ≥ amount_total.
        for po in self:
            if po.budget_id and po.budget_id.auto_block_overrun:
                remaining = po.budget_id.remaining_amount
                if po.amount_total > remaining:
                    if po.approval_state != "approved":
                        po.approval_state = "pending"
                        raise UserError(_(
                            "PO total %s exceeds budget remaining %s. "
                            "Approval required before confirming."
                        ) % (po.amount_total, remaining))
        return super().button_confirm()
