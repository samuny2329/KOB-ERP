# -*- coding: utf-8 -*-
"""Extract structured fields from MEA SIGN_*.pdf bills.

Parsing strategy: pdfplumber → fallback PyPDF2 → regex pattern match.
Patterns are derived from validated bills in this project (KOB / BTV / CMN).

Confidence score per field is averaged into ``extraction_confidence`` 0..1.
Records below 0.7 are flagged ``state='manual_review'``.
"""
import base64
import io
import logging
import re
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)

try:
    import pdfplumber  # type: ignore
    _HAS_PDFPLUMBER = True
except ImportError:  # pragma: no cover
    pdfplumber = None
    _HAS_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader  # type: ignore
    _HAS_PYPDF2 = True
except ImportError:  # pragma: no cover
    try:
        from pypdf import PdfReader  # type: ignore
        _HAS_PYPDF2 = True
    except ImportError:
        _HAS_PYPDF2 = False
        PdfReader = None


# Buddhist Era → Gregorian
BE_OFFSET = 543

# Field regexes — order matters (more specific first).
_R_INVOICE = re.compile(r"(\d{11})\s+\d{2}/\d{2}/\d{2}\s+\d")
_R_CA = re.compile(r"(\d{9})\s+(\d{8})")
_R_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2})")
_R_TOTAL = re.compile(r"รวมเงินที่ต้องชำระทั้งสิ้น[^0-9]*([\d,]+\.\d{2})")
_R_KWH = re.compile(r"\d{2}/\d{2}/\d{2}\s+\d+\s+\d+\s+([\d,]+)\s+\d\.\d\.\d")
_R_FT = re.compile(r"\d\.\d\.\d\s+\d?\s*(\d\.\d{4})")
_R_TARIFF = re.compile(r"(\d\.\d\.\d)")
_R_PEAK_KWH = re.compile(r"On Peak\s+([\d,]+)\s+หน่วย")
_R_OFFPEAK_KWH = re.compile(r"Off Peak\s+([\d,]+)\s+หน่วย")


class MeaPdfExtractor(models.AbstractModel):
    _name = "mea.pdf.extractor"
    _description = "MEA Bill PDF Extractor"

    # ---------- Public ----------
    @api.model
    def extract_from_attachment(self, attachment):
        """Extract bill fields from an ``ir.attachment`` record.

        Returns dict with keys: ``ca_number``, ``meter_id``, ``invoice_no``,
        ``billing_date``, ``kwh_total``, ``kwh_on_peak``, ``kwh_off_peak``,
        ``ft_rate``, ``total_amount``, ``tariff_code``, ``confidence``,
        ``raw_text``, ``error`` (when extraction failed).
        """
        if not attachment or not attachment.datas:
            return {"error": "Empty attachment"}

        try:
            raw_bytes = base64.b64decode(attachment.datas)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Decode failed: {exc}"}

        text = self._pdf_to_text(raw_bytes)
        if not text:
            return {"error": "Could not extract text from PDF"}

        return self._parse_text(text)

    @api.model
    def extract_from_bytes(self, raw_bytes):
        """Test-friendly entry: parse from raw PDF bytes."""
        text = self._pdf_to_text(raw_bytes)
        if not text:
            return {"error": "Could not extract text from PDF"}
        return self._parse_text(text)

    # ---------- Internal ----------
    @api.model
    def _pdf_to_text(self, raw_bytes):
        if _HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("pdfplumber failed: %s", exc)
        if _HAS_PYPDF2:
            try:
                reader = PdfReader(io.BytesIO(raw_bytes))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("PyPDF2 failed: %s", exc)
        return ""

    @api.model
    def _parse_text(self, text):
        result = {
            "ca_number": None,
            "meter_id": None,
            "invoice_no": None,
            "billing_date": None,
            "tariff_code": None,
            "kwh_total": None,
            "kwh_on_peak": None,
            "kwh_off_peak": None,
            "kwh_prev": None,
            "kwh_curr": None,
            "ft_rate": None,
            "total_amount": None,
            "raw_text": text[:8000],
            "confidence": 0.0,
        }
        hits = 0
        total_checks = 7

        # CA + Meter (printed twice — once in summary, once in delivery slip)
        m = _R_CA.search(text)
        if m:
            result["ca_number"] = m.group(1)
            result["meter_id"] = m.group(2)
            hits += 1

        # Invoice / billing reference + reading date
        m_inv = _R_INVOICE.search(text)
        if m_inv:
            result["invoice_no"] = m_inv.group(1)
            hits += 1

        # Billing date — first DD/MM/YY (Buddhist Era 25xx → Gregorian)
        # MEA bills print BE year with millennium dropped, e.g. "30/04/69" = BE 2569 = AD 2026
        m_dt = _R_DATE.search(text)
        if m_dt:
            d, mo, y = (int(x) for x in m_dt.groups())
            try:
                result["billing_date"] = date(1957 + y, mo, d)
                hits += 1
            except ValueError:
                pass

        # Tariff code (3.2.3 / 2.1.2 / etc.)
        m_t = _R_TARIFF.search(text)
        if m_t:
            result["tariff_code"] = m_t.group(1)
            hits += 1

        # kWh total — captured from meter reading line "...{kwh} {tariff}..."
        m_k = _R_KWH.search(text)
        if m_k:
            result["kwh_total"] = float(m_k.group(1).replace(",", ""))
            hits += 1

        # On / Off peak (TOU only)
        m_p = _R_PEAK_KWH.search(text)
        if m_p:
            result["kwh_on_peak"] = float(m_p.group(1).replace(",", ""))
        m_op = _R_OFFPEAK_KWH.search(text)
        if m_op:
            result["kwh_off_peak"] = float(m_op.group(1).replace(",", ""))

        # Ft rate (THB/kWh, e.g. 0.0972)
        m_ft = _R_FT.search(text)
        if m_ft:
            result["ft_rate"] = float(m_ft.group(1))
            hits += 1

        # Total amount
        m_total = _R_TOTAL.search(text)
        if m_total:
            result["total_amount"] = float(m_total.group(1).replace(",", ""))
            hits += 1

        # Previous / current readings — 2 numbers between meter date + kWh on the same row
        m_pcr = re.search(
            r"(\d{2}/\d{2}/\d{2})\s+(\d{4,7})\s+(\d{4,7})\s+(\d[\d,]*)\s+(\d\.\d\.\d)",
            text,
        )
        if m_pcr:
            result["kwh_curr"] = float(m_pcr.group(2).replace(",", ""))
            result["kwh_prev"] = float(m_pcr.group(3).replace(",", ""))

        result["confidence"] = round(hits / total_checks, 2)
        return result
