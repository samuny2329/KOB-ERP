# -*- coding: utf-8 -*-
"""Cost allocation — split a shared expense across companies in the group."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobCostAllocation(models.Model):
    _name = "kob.cost.allocation"
    _description = "Cost Allocation"
    _order = "period_year desc, period_month desc"

    name = fields.Char(required=True)
    parent_company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="parent_company_id.currency_id", store=True, readonly=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    total_amount = fields.Monetary(currency_field="currency_id", required=True)
    basis = fields.Selection(
        [
            ("revenue", "Revenue"),
            ("headcount", "Headcount"),
            ("sqm", "Floor area (sqm)"),
            ("manual", "Manual"),
            ("fixed", "Fixed shares"),
        ],
        default="manual",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    posted_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many("kob.cost.allocation.line", "allocation_id")
    note = fields.Text()

    def action_calculate(self):
        for alloc in self:
            if alloc.state not in ("draft", "calculated"):
                raise UserError(_("Cannot calculate in state %s.") % alloc.state)
            # Compute amount = total × share_pct / 100
            for line in alloc.line_ids:
                line.amount = round(
                    float(alloc.total_amount) * float(line.share_pct or 0)
                    / 100.0,
                    2,
                )
            total_pct = sum(alloc.line_ids.mapped("share_pct"))
            if abs(total_pct - 100.0) > 0.01:
                raise UserError(_(
                    "Share percentages must sum to 100% (currently %s)."
                ) % total_pct)
            alloc.state = "calculated"

    def action_post(self):
        for alloc in self:
            if alloc.state != "calculated":
                raise UserError(_("Calculate before posting."))
            alloc.write({
                "state": "posted",
                "posted_at": fields.Datetime.now(),
            })

    def action_cancel(self):
        for alloc in self:
            if alloc.state == "posted":
                raise UserError(_("Cannot cancel a posted allocation."))
            alloc.state = "cancelled"


class KobCostAllocationLine(models.Model):
    _name = "kob.cost.allocation.line"
    _description = "Cost Allocation Line"

    allocation_id = fields.Many2one(
        "kob.cost.allocation", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    share_pct = fields.Float(digits=(6, 4), required=True)
    amount = fields.Monetary(currency_field="currency_id", readonly=True)
    move_id = fields.Many2one("account.move", string="Journal Entry")
    currency_id = fields.Many2one(
        related="allocation_id.currency_id", store=True, readonly=True,
    )
