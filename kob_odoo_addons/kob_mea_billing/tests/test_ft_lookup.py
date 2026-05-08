# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("kob_mea_billing", "kob_mea_ft")
class TestFtLookup(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Ft = self.env["mea.ft.period"]

    def test_lookup_q3_2025(self):
        period = self.Ft.get_for_date(date(2025, 11, 15))
        self.assertTrue(period)
        self.assertEqual(period.ft_rate, 15.72)

    def test_lookup_q1_2026(self):
        period = self.Ft.get_for_date(date(2026, 2, 1))
        self.assertEqual(period.ft_rate, 9.72)

    def test_lookup_outside_range(self):
        period = self.Ft.get_for_date(date(2020, 1, 1))
        self.assertFalse(period)

    def test_no_overlap_constraint(self):
        with self.assertRaises(ValidationError):
            self.Ft.create({
                "period_start": "2026-01-15",
                "period_end": "2026-02-15",
                "ft_rate": 99.0,
            })

    def test_invalid_range(self):
        with self.assertRaises(ValidationError):
            self.Ft.create({
                "period_start": "2030-12-01",
                "period_end": "2030-11-01",
                "ft_rate": 1.0,
            })
