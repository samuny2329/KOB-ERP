# -*- coding: utf-8 -*-
"""Smoke tests for the PDF extractor.

Real-bill verification is not run in CI (PDFs are not committed).
Place a test PDF in this folder named ``sample.pdf`` to exercise full parse.
"""
import os

from odoo.tests.common import TransactionCase, tagged


@tagged("kob_mea_billing", "kob_mea_pdf")
class TestPdfExtractor(TransactionCase):

    def setUp(self):
        super().setUp()
        self.extractor = self.env["mea.pdf.extractor"]

    def test_empty_bytes_returns_error(self):
        result = self.extractor.extract_from_bytes(b"")
        self.assertIn("error", result)

    def test_garbage_bytes_returns_error(self):
        result = self.extractor.extract_from_bytes(b"not a real pdf")
        self.assertIn("error", result)

    def test_parse_text_minimal_fields(self):
        """Direct text-parser test with MEA-like text (matches real PDF layout)."""
        sample = (
            "บัญชีแสดงสัญญา CA/Ref No.1 รหัสเครื่องวัดฯ Installation\n"
            "015634979 96484442\n"
            "25819838376 30/04/69 386904 377036 9,868 3.2.3 0.0972\n"
            "On Peak 7,311 หน่วย\n"
            "Off Peak 2,557 หน่วย\n"
            "รวมเงินที่ต้องชำระทั้งสิ้น 53,230.79 บาท\n"
        )
        result = self.extractor._parse_text(sample)
        self.assertEqual(result["ca_number"], "015634979")
        self.assertEqual(result["meter_id"], "96484442")
        self.assertEqual(result["kwh_total"], 9868)
        self.assertEqual(result["kwh_on_peak"], 7311)
        self.assertEqual(result["kwh_off_peak"], 2557)
        self.assertEqual(result["ft_rate"], 0.0972)
        self.assertEqual(result["total_amount"], 53230.79)
        self.assertGreaterEqual(result["confidence"], 0.7)

    def test_parse_text_be_date_conversion(self):
        sample = "12345678901 30/04/69 100 50 50 2.1.2 0.0972"
        result = self.extractor._parse_text(sample)
        self.assertIsNotNone(result["billing_date"])
        # 30/04/69 BE → 30 April 2026 AD
        self.assertEqual(result["billing_date"].year, 2026)
        self.assertEqual(result["billing_date"].month, 4)
        self.assertEqual(result["billing_date"].day, 30)

    def test_real_pdf_smoke(self):
        path = os.path.join(os.path.dirname(__file__), "sample.pdf")
        if not os.path.exists(path):
            self.skipTest("sample.pdf not provided in tests/ folder")
        with open(path, "rb") as f:
            data = f.read()
        result = self.extractor.extract_from_bytes(data)
        self.assertNotIn("error", result)
        self.assertIsNotNone(result["ca_number"])
