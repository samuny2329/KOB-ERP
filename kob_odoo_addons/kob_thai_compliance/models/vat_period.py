# -*- coding: utf-8 -*-
"""VAT period (ภพ.30 — monthly VAT return).

Ported from ``backend/modules/accounting/models_advanced.py``
(``VatPeriod`` + ``VatLine``).

Aggregates output VAT (charged on sales) and input VAT (paid on
purchases) for one calendar month per company.  ``net_payable`` is the
amount RD expects on the 15th (or 23rd via e-filing) of next month.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobVatPeriod(models.Model):
    _name = "kob.vat.period"
    _description = "VAT Period (ภพ.30)"
    _order = "period_year desc, period_month desc"
    _sql_constraints = [
        (
            "uniq_vat_period",
            "unique(company_id, period_year, period_month, form_type)",
            "VAT period already exists for this company / month / form type.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    form_type = fields.Selection(
        [
            ("pp30", "ภ.พ.30 — Domestic VAT return"),
            ("pp36", "ภ.พ.36 — Reverse-charge / foreign VAT"),
        ],
        default="pp30",
        required=True,
        string="Form Type",
        help="ภ.พ.30 covers domestic output/input VAT. "
             "ภ.พ.36 covers reverse-charge VAT on services from "
             "non-resident vendors (paid before remittance abroad).",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("submitted", "Submitted"),
            ("amended", "Amended"),
            ("settled", "Settled"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    output_vat = fields.Monetary(currency_field="currency_id", readonly=True)
    input_vat = fields.Monetary(currency_field="currency_id", readonly=True)
    net_payable = fields.Monetary(currency_field="currency_id", readonly=True)
    credit_carried_forward = fields.Monetary(currency_field="currency_id")
    submitted_at = fields.Datetime()
    submitted_by = fields.Many2one("res.users")
    rd_receipt_number = fields.Char(string="RD Receipt No.")
    note = fields.Text()
    line_ids = fields.One2many("kob.vat.line", "period_id", string="Lines")

    def action_calculate(self):
        for rec in self:
            if rec.state not in ("draft", "calculated", "amended"):
                raise UserError(
                    _("Cannot calculate period in state %s.") % rec.state,
                )
            output = sum(rec.line_ids.filtered(
                lambda l: l.direction == "output").mapped("vat_amount"))
            input_ = sum(rec.line_ids.filtered(
                lambda l: l.direction == "input").mapped("vat_amount"))
            rec.output_vat = output
            rec.input_vat = input_
            rec.net_payable = output - input_
            rec.state = "calculated"

    def action_submit(self):
        for rec in self:
            if rec.state != "calculated":
                raise UserError(
                    _("Only calculated periods can be submitted."),
                )
            rec.write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
                "submitted_by": self.env.user.id,
            })

    def action_settle(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(
                    _("Only submitted periods can be settled."),
                )
            rec.state = "settled"

    def action_amend(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(
                    _("Only submitted periods can be amended."),
                )
            rec.state = "amended"

    def action_cancel(self):
        for rec in self:
            if rec.state in ("settled",):
                raise UserError(
                    _("Cannot cancel a settled period."),
                )
            rec.state = "cancelled"


class KobVatLine(models.Model):
    _name = "kob.vat.line"
    _description = "VAT Line"

    period_id = fields.Many2one(
        "kob.vat.period", ondelete="cascade", required=True, index=True,
    )
    currency_id = fields.Many2one(
        related="period_id.currency_id", store=True, readonly=True,
    )
    direction = fields.Selection(
        [("input", "Input (purchases)"), ("output", "Output (sales)")],
        required=True,
    )
    document_date = fields.Date(required=True)
    counterparty_name = fields.Char(required=True)
    counterparty_tax_id = fields.Char()
    invoice_number = fields.Char()
    base_amount = fields.Monetary(currency_field="currency_id", required=True)
    vat_amount = fields.Monetary(currency_field="currency_id", required=True)
    total_amount = fields.Monetary(currency_field="currency_id", required=True)
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        help="Source journal entry (customer invoice or vendor bill).",
    )
