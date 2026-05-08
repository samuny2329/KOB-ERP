# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.exceptions import UserError


class MeaPdfImportWizard(models.TransientModel):
    _name = "mea.pdf.import.wizard"
    _description = "MEA PDF Import Wizard"

    pdf_file = fields.Binary(string="MEA Bill PDF", required=True)
    pdf_filename = fields.Char()
    meter_id = fields.Many2one(
        "mea.meter",
        help="Optional. If empty, the meter is matched by CA Number from the PDF.",
    )
    auto_confirm = fields.Boolean(
        string="Auto-Confirm",
        default=False,
        help="When extraction confidence ≥ 0.7, set state to 'confirmed' "
             "(or 'anomaly' if variance > 20%). Otherwise stays 'manual_review'.",
    )

    preview_text = fields.Text(readonly=True)
    preview_summary = fields.Text(readonly=True)
    bill_history_id = fields.Many2one("mea.bill.history", readonly=True)

    def action_preview(self):
        self.ensure_one()
        if not self.pdf_file:
            raise UserError("Please attach a MEA bill PDF first.")
        raw = base64.b64decode(self.pdf_file)
        result = self.env["mea.pdf.extractor"].extract_from_bytes(raw)
        if result.get("error"):
            raise UserError(result["error"])
        summary = (
            f"CA Number      : {result.get('ca_number')}\n"
            f"Meter ID       : {result.get('meter_id')}\n"
            f"Invoice No.    : {result.get('invoice_no')}\n"
            f"Billing Date   : {result.get('billing_date')}\n"
            f"Tariff         : {result.get('tariff_code')}\n"
            f"kWh Total      : {result.get('kwh_total')}\n"
            f"On-Peak kWh    : {result.get('kwh_on_peak')}\n"
            f"Off-Peak kWh   : {result.get('kwh_off_peak')}\n"
            f"Ft Rate        : {result.get('ft_rate')}\n"
            f"Total Amount   : {result.get('total_amount')}\n"
            f"Confidence     : {result.get('confidence')}\n"
        )
        self.write({
            "preview_summary": summary,
            "preview_text": result.get("raw_text", ""),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "mea.pdf.import.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_import(self):
        self.ensure_one()
        if not self.pdf_file:
            raise UserError("Please attach a MEA bill PDF first.")
        raw = base64.b64decode(self.pdf_file)
        result = self.env["mea.pdf.extractor"].extract_from_bytes(raw)
        if result.get("error"):
            raise UserError(result["error"])

        # Match meter
        meter = self.meter_id
        if not meter and result.get("ca_number"):
            meter = self.env["mea.meter"].search(
                [("ca_number", "=", result["ca_number"])], limit=1
            )
        if not meter:
            raise UserError(
                "Could not match meter — set Meter manually or create one with "
                f"CA={result.get('ca_number')}, Meter ID={result.get('meter_id')}."
            )

        billing_date = result.get("billing_date")
        if not billing_date:
            raise UserError("Could not extract billing date from PDF.")
        # Normalize to first of month
        billing_month = billing_date.replace(day=1)

        existing = self.env["mea.bill.history"].search([
            ("meter_id", "=", meter.id),
            ("billing_month", "=", billing_month),
        ], limit=1)

        confidence = result.get("confidence") or 0.0
        if self.auto_confirm and confidence >= 0.7:
            target_state = "confirmed"
        elif confidence < 0.7:
            target_state = "manual_review"
        else:
            target_state = "draft"

        # Persist source PDF as ir.attachment
        att = self.env["ir.attachment"].create({
            "name": self.pdf_filename or f"MEA_{meter.ca_number}_{billing_month}.pdf",
            "datas": self.pdf_file,
            "res_model": "mea.bill.history",
            "type": "binary",
            "mimetype": "application/pdf",
        })

        vals = {
            "meter_id": meter.id,
            "billing_month": billing_month,
            "invoice_no": result.get("invoice_no"),
            "reading_date_end": billing_date,
            "kwh_total": result.get("kwh_total") or 0.0,
            "kwh_on_peak": result.get("kwh_on_peak") or 0.0,
            "kwh_off_peak": result.get("kwh_off_peak") or 0.0,
            "kwh_prev": result.get("kwh_prev") or 0.0,
            "kwh_curr": result.get("kwh_curr") or 0.0,
            "ft_rate": result.get("ft_rate") or 0.0,
            "total_amount": result.get("total_amount") or 0.0,
            "source": "pdf_extract",
            "extraction_confidence": confidence,
            "attachment_id": att.id,
            "state": target_state,
            "raw_text": result.get("raw_text", ""),
        }

        if existing:
            existing.write(vals)
            history = existing
            att.res_id = history.id
        else:
            history = self.env["mea.bill.history"].create(vals)
            att.res_id = history.id

        self.bill_history_id = history.id
        return {
            "type": "ir.actions.act_window",
            "name": "Imported Bill",
            "res_model": "mea.bill.history",
            "view_mode": "form",
            "res_id": history.id,
            "target": "current",
        }
