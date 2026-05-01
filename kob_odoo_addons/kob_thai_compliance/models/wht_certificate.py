# -*- coding: utf-8 -*-
"""WHT certificate (ภงด.3 / ภงด.53 / ภงด.2 / ภงด.1ก).

Ported from ``backend/modules/accounting/models_advanced.py``
(``WhtCertificate``).  In Odoo we plug into the existing accounting:

  * ``journal_entry_id`` → ``account.move``
  * ``payee`` → ``res.partner`` (vendor)

The certificate is a printable / e-filed document KOB hands to the
supplier when withholding tax is applied at payment time.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Standard Thai income type codes printed on the WHT certificate.
INCOME_TYPE_CODES = [
    ("40_1", "40(1) — เงินเดือน ค่าจ้าง"),
    ("40_2", "40(2) — ค่าธรรมเนียม คอมมิชชั่น"),
    ("40_3", "40(3) — ค่าลิขสิทธิ์"),
    ("40_4_a", "40(4)(ก) — ดอกเบี้ย"),
    ("40_4_b", "40(4)(ข) — เงินปันผล"),
    ("40_5", "40(5) — ค่าเช่าทรัพย์สิน"),
    ("40_6", "40(6) — วิชาชีพอิสระ"),
    ("40_7", "40(7) — รับเหมา"),
    ("40_8", "40(8) — บริการอื่น / โฆษณา / ขนส่ง"),
]


class KobWhtCertificate(models.Model):
    """A WHT certificate issued by a KOB company to a payee."""

    _name = "kob.wht.certificate"
    _description = "WHT Certificate (ภงด.3 / ภงด.53)"
    _order = "issue_date desc, sequence_number desc"
    _sql_constraints = [
        (
            "uniq_wht_seq",
            "unique(company_id, form_type, period_year, sequence_number)",
            "Sequence number already used for this form/year.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )

    form_type = fields.Selection(
        [
            ("pnd1a", "PND1A — Annual employee WHT"),
            ("pnd2", "PND2 — Investment income"),
            ("pnd3", "PND3 — Service WHT (individual)"),
            ("pnd53", "PND53 — Corporate WHT"),
        ],
        required=True,
        default="pnd3",
    )
    sequence_number = fields.Integer(
        required=True,
        help="Per-company-per-year sequential certificate number.",
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    issue_date = fields.Date(required=True, default=fields.Date.context_today)

    payee_partner_id = fields.Many2one(
        "res.partner",
        string="Payee",
        help="Vendor or contractor receiving the payment.",
    )
    payee_name = fields.Char(required=True)
    payee_tax_id = fields.Char(string="Tax ID", required=True)
    payee_address = fields.Text()

    income_type_code = fields.Selection(INCOME_TYPE_CODES, required=True)
    income_description = fields.Char()
    gross_amount = fields.Monetary(currency_field="currency_id", required=True)
    wht_rate_pct = fields.Float(
        string="WHT Rate (%)",
        digits=(6, 4),
        required=True,
        help="Common rates: 1% (transport), 2% (advertising), 3% (services), "
             "5% (rent), 10% (dividend), 15% (interest, royalty).",
    )
    wht_amount = fields.Monetary(currency_field="currency_id", required=True)

    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        ondelete="set null",
        help="Journal entry that booked the WHT liability.",
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Payment",
        ondelete="set null",
        help="Vendor payment from which the WHT was deducted.",
    )
    note = fields.Text()

    @api.onchange("payee_partner_id")
    def _onchange_payee_partner(self):
        for rec in self:
            p = rec.payee_partner_id
            if p:
                rec.payee_name = p.name
                rec.payee_tax_id = p.vat or rec.payee_tax_id
                rec.payee_address = (
                    "%s\n%s %s %s" % (
                        p.street or "", p.city or "",
                        p.state_id.name or "", p.zip or "",
                    )
                ).strip()

    @api.onchange("gross_amount", "wht_rate_pct")
    def _onchange_compute_wht(self):
        for rec in self:
            if rec.gross_amount and rec.wht_rate_pct:
                rec.wht_amount = round(
                    float(rec.gross_amount) * float(rec.wht_rate_pct) / 100.0, 2,
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Auto-assign sequence_number per (company, form_type, year)
        # if not provided.
        for vals in vals_list:
            if vals.get("sequence_number"):
                continue
            company_id = vals.get("company_id") or self.env.company.id
            form_type = vals.get("form_type", "pnd3")
            period_year = vals.get(
                "period_year", fields.Date.context_today(self).year,
            )
            last = self.search(
                [
                    ("company_id", "=", company_id),
                    ("form_type", "=", form_type),
                    ("period_year", "=", period_year),
                ],
                order="sequence_number desc",
                limit=1,
            )
            vals["sequence_number"] = (last.sequence_number or 0) + 1
        return super().create(vals_list)

    def name_get(self):
        out = []
        for rec in self:
            out.append((
                rec.id,
                "%s/%04d-%05d %s" % (
                    rec.form_type.upper(), rec.period_year,
                    rec.sequence_number, rec.payee_name or "",
                ),
            ))
        return out
