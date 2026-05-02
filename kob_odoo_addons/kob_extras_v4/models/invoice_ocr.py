# -*- coding: utf-8 -*-
"""Phase 45 — Invoice OCR pipeline.

Queue model for vendor bill PDFs awaiting OCR extraction. Pluggable backend
(Tesseract-local, Google Vision, AWS Textract, or KOB AI gateway) — set
`ocr_backend` config param. This model handles state machine + audit log;
actual extraction is delegated to a hookable method.
"""
import base64
import re

from odoo import api, fields, models, _


class KobInvoiceOcrQueue(models.Model):
    _name = "kob.invoice.ocr.queue"
    _description = "Invoice OCR Queue"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(default=lambda s: s._default_name(), readonly=True)
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade")
    file_name = fields.Char(related="attachment_id.name", store=True)
    pdf_data = fields.Binary(related="attachment_id.datas", readonly=True)
    state = fields.Selection(
        [("queued", "Queued"), ("processing", "Processing"),
         ("done", "Done"), ("review", "Needs Review"), ("failed", "Failed")],
        default="queued", tracking=True,
    )
    extracted_partner_name = fields.Char(string="Vendor Name (extracted)")
    extracted_partner_id = fields.Many2one("res.partner")
    extracted_vat = fields.Char(string="Tax ID (extracted)")
    extracted_invoice_number = fields.Char(string="Invoice # (extracted)")
    extracted_date = fields.Date(string="Invoice Date (extracted)")
    extracted_amount = fields.Float(string="Amount (extracted)")
    extracted_currency = fields.Char(default="THB")
    confidence = fields.Float(help="0.0–1.0; below 0.7 → review")
    error_message = fields.Text()
    bill_id = fields.Many2one("account.move", string="Created Bill", readonly=True)
    backend = fields.Char(default=lambda s: s._default_backend())

    @api.model
    def _default_name(self):
        seq = self.env["ir.sequence"].next_by_code("kob.invoice.ocr.queue") or "/"
        return f"OCR/{seq}"

    @api.model
    def _default_backend(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "kob.ocr_backend", default="stub")

    # ---- Public actions ------------------------------------------------------

    def action_process(self):
        for r in self:
            if r.state not in ("queued", "failed"):
                continue
            r.state = "processing"
            try:
                data = r._extract()
                r.write(data)
                # Try to match partner by VAT first, then by name
                partner = self._match_partner(data.get("extracted_vat"),
                                              data.get("extracted_partner_name"))
                if partner:
                    r.extracted_partner_id = partner.id
                conf = data.get("confidence", 0.0)
                r.state = "done" if conf >= 0.7 and partner else "review"
            except Exception as e:
                r.write({"state": "failed", "error_message": str(e)})

    def action_create_bill(self):
        self.ensure_one()
        if not self.extracted_partner_id:
            raise self.env["ir.exceptions"].UserError(_("Match a vendor first."))
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.extracted_partner_id.id,
            "ref": self.extracted_invoice_number,
            "invoice_date": self.extracted_date,
            "invoice_line_ids": [(0, 0, {
                "name": f"OCR import {self.name}",
                "quantity": 1,
                "price_unit": self.extracted_amount or 0.0,
            })],
        })
        # Attach the original PDF to the bill
        self.attachment_id.write({
            "res_model": "account.move",
            "res_id": bill.id,
        })
        self.bill_id = bill.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": bill.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def cron_process_queue(self):
        queued = self.search([("state", "in", ["queued", "failed"])], limit=20)
        queued.action_process()
        return len(queued)

    # ---- Backend hooks -------------------------------------------------------

    def _extract(self):
        """Override in plugin module to call real OCR backend.

        Stub returns empty fields with low confidence for review.
        """
        backend = self.backend or "stub"
        method = getattr(self, f"_extract_{backend}", None)
        if method:
            return method()
        return self._extract_stub()

    def _extract_stub(self):
        # Try cheap regex on filename as a baseline
        fname = self.file_name or ""
        inv_match = re.search(r"(INV[-_]?\d+)", fname, re.IGNORECASE)
        return {
            "extracted_invoice_number": inv_match.group(1) if inv_match else "",
            "confidence": 0.3,
        }

    def _match_partner(self, vat, name):
        Partner = self.env["res.partner"]
        if vat:
            p = Partner.search([("vat", "=", vat)], limit=1)
            if p:
                return p
        if name:
            p = Partner.search([("name", "ilike", name),
                                ("supplier_rank", ">", 0)], limit=1)
            if p:
                return p
        return Partner.browse()
