# -*- coding: utf-8 -*-
"""Procurement budget pots that gate PO approval."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobProcurementBudget(models.Model):
    _name = "kob.procurement.budget"
    _description = "Procurement Budget"
    _order = "fiscal_year desc, name"

    name = fields.Char(required=True)
    department = fields.Char()
    project_code = fields.Char(index=True)
    project_id = fields.Many2one(
        "project.project", string="Project",
        help="Link this budget to an Odoo Project. Useful for tracking "
             "spending against a specific initiative (campaign, R&D, etc).",
    )
    expenditure_type = fields.Selection(
        [
            ("capex", "CapEx (Capital Expenditure)"),
            ("opex", "OpEx (Operating Expenditure)"),
        ],
        string="Type",
        default="opex",
        required=True,
        help="CapEx = long-life assets (equipment, building, perpetual "
             "software, vehicle). OpEx = recurring operating costs "
             "(salaries, rent, marketing, subscriptions).",
    )
    category = fields.Selection(
        [
            # CapEx
            ("capex_equipment", "Equipment & Machinery"),
            ("capex_building", "Building & Office Improvements"),
            ("capex_software", "Software License (Perpetual)"),
            ("capex_vehicle", "Vehicle Purchase"),
            ("capex_it", "IT Hardware"),
            # OpEx
            ("opex_salaries", "Salaries & Wages"),
            ("opex_rent", "Rent & Utilities"),
            ("opex_marketing", "Marketing & Advertising"),
            ("opex_travel", "Travel & Entertainment"),
            ("opex_training", "Training & Development"),
            ("opex_subscription", "Software Subscriptions"),
            ("opex_maintenance", "Maintenance & Repair"),
            ("opex_supplies", "Office Supplies"),
            ("opex_professional", "Professional Services"),
            ("opex_other", "Other Operating"),
        ],
        string="Category",
        help="Granular bucket within CapEx/OpEx. Maps 1:1 with KOB "
             "Notion category list.",
    )
    fiscal_year = fields.Integer(required=True)
    period_from = fields.Date(required=True)
    period_to = fields.Date(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    total_budget = fields.Monetary(currency_field="currency_id", required=True)
    committed_amount = fields.Monetary(
        currency_field="currency_id", readonly=True,
        help="Sum of confirmed POs charged to this budget.",
    )
    spent_amount = fields.Monetary(
        currency_field="currency_id", readonly=True,
        help="Sum of paid POs / received receipts.",
    )
    remaining_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_remaining",
        store=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    auto_block_overrun = fields.Boolean(
        default=True,
        help="When true, POs exceeding remaining budget are blocked from "
             "confirmation until manually approved.",
    )
    owner_id = fields.Many2one(
        "res.users", default=lambda s: s.env.user,
    )
    purchase_order_ids = fields.One2many(
        "purchase.order", "budget_id", string="Purchase Orders",
    )
    note = fields.Text()

    @api.depends("total_budget", "committed_amount")
    def _compute_remaining(self):
        for b in self:
            b.remaining_amount = float(b.total_budget or 0) - float(
                b.committed_amount or 0,
            )

    @api.constrains("period_from", "period_to")
    def _check_period(self):
        for b in self:
            if b.period_from and b.period_to and b.period_from > b.period_to:
                raise UserError(_("Period start must be ≤ period end."))

    def action_activate(self):
        for b in self:
            if b.state != "draft":
                raise UserError(_("Only draft budgets can be activated."))
            b.state = "active"

    def action_close(self):
        for b in self:
            if b.state != "active":
                raise UserError(_("Only active budgets can be closed."))
            b.state = "closed"

    def action_cancel(self):
        for b in self:
            if b.state == "closed":
                raise UserError(_("Closed budgets cannot be cancelled."))
            b.state = "cancelled"

    def refresh_committed(self):
        """Recompute committed_amount from confirmed POs."""
        for b in self:
            POs = b.purchase_order_ids.filtered(
                lambda p: p.state in ("purchase", "done"),
            )
            b.committed_amount = sum(POs.mapped("amount_total"))
            paid = POs.filtered(lambda p: p.invoice_status == "invoiced")
            b.spent_amount = sum(paid.mapped("amount_total"))
