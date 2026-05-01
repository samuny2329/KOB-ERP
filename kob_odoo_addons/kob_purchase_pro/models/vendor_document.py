# -*- coding: utf-8 -*-
"""Vendor compliance documents (ISO, audit, insurance, contract)."""

from datetime import timedelta

from odoo import api, fields, models, _


DOC_TYPES = [
    ("iso_cert", "ISO Certification"),
    ("food_safety", "Food Safety Certificate"),
    ("factory_audit", "Factory Audit Report"),
    ("insurance", "Insurance"),
    ("contract", "Contract / NDA"),
    ("tax_cert", "Tax Certificate"),
    ("other", "Other"),
]


class KobVendorDocument(models.Model):
    _name = "kob.vendor.document"
    _description = "Vendor Compliance Document"
    _order = "expiry_date asc"

    vendor_id = fields.Many2one(
        "res.partner", string="Vendor", required=True, ondelete="cascade",
        domain=[("supplier_rank", ">", 0)],
    )
    doc_type = fields.Selection(DOC_TYPES, required=True, default="iso_cert")
    title = fields.Char(required=True)
    reference = fields.Char()
    issued_date = fields.Date()
    expiry_date = fields.Date(index=True)
    alert_days_before = fields.Integer(default=30)
    file_url = fields.Char()
    note = fields.Text()
    active = fields.Boolean(default=True)
    is_expiring = fields.Boolean(
        compute="_compute_is_expiring", store=False,
        help="True when within alert window before expiry.",
    )

    @api.depends("expiry_date", "alert_days_before", "active")
    def _compute_is_expiring(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active or not rec.expiry_date:
                rec.is_expiring = False
                continue
            cutoff = today + timedelta(days=rec.alert_days_before or 0)
            rec.is_expiring = bool(rec.expiry_date and rec.expiry_date <= cutoff)

    @api.model
    def _cron_check_expiry(self):
        """Daily cron — log activities for soon-to-expire docs."""
        today = fields.Date.context_today(self)
        docs = self.search([("active", "=", True), ("expiry_date", "!=", False)])
        for d in docs:
            cutoff = today + timedelta(days=d.alert_days_before or 0)
            if d.expiry_date <= cutoff and d.expiry_date >= today:
                d.vendor_id.message_post(
                    body=_(
                        "Vendor document <b>%s</b> (%s) expires on %s."
                    ) % (d.title, d.doc_type, d.expiry_date),
                )
