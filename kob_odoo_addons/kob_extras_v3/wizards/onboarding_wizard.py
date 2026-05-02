# -*- coding: utf-8 -*-
"""Phase 40 — Onboarding wizard for new company first-run setup."""
from odoo import api, fields, models


class KobOnboardingWizard(models.TransientModel):
    _name = "kob.onboarding.wizard"
    _description = "KOB ERP First-Run Setup"

    company_name = fields.Char(required=True)
    vat = fields.Char(string="Tax ID (TIN)")
    phone = fields.Char()
    email = fields.Char()
    address_street = fields.Char()
    address_city = fields.Char()
    base_currency = fields.Many2one(
        "res.currency", default=lambda s: s.env.ref("base.THB"),
    )
    fiscal_year_start_month = fields.Integer(default=1)
    setup_default_journals = fields.Boolean(default=True)
    setup_default_taxes = fields.Boolean(default=True)
    setup_sample_warehouse = fields.Boolean(default=True)
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done")],
        default="draft",
    )

    def action_run(self):
        self.ensure_one()
        Company = self.env["res.company"]
        co = Company.search([("name", "=", self.company_name)], limit=1)
        if not co:
            co = Company.create({
                "name": self.company_name,
                "vat": self.vat,
                "phone": self.phone,
                "email": self.email,
                "street": self.address_street,
                "city": self.address_city,
                "currency_id": self.base_currency.id,
            })
        self.state = "done"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Setup Complete",
                "message": f"Company '{co.name}' configured. Next: assign warehouse + journals.",
                "sticky": True,
                "type": "success",
            },
        }
