# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("kob_mea_billing", "kob_mea_calc")
class TestMeaCalculator(TransactionCase):

    def setUp(self):
        super().setUp()
        self.calc = self.env["mea.calculator"]
        # Force test-known rates instead of relying on seed (which may have been
        # frozen by noupdate=1 on first install). Test-isolation: each test
        # validates calculator logic against a fixed contract.
        self.tariff_tou = self.env.ref("kob_mea_billing.tariff_3_2_3").sudo()
        self.tariff_tou.write({
            "peak_rate": 4.3300,
            "off_peak_rate": 2.6400,
            "service_charge": 312.24,
            "demand_charge": 210.00,
        })
        self.tariff_flat = self.env.ref("kob_mea_billing.tariff_2_1_2")

    # -------------- TOU 3.2.3 --------------
    def test_tou_april_2026_kob_kk16(self):
        """KOB-KK16 April 2026: 7,262 kWh actual = 37,947.33; verify within 3%."""
        meter = self.env["mea.meter"].new({"tariff_id": self.tariff_tou.id})
        result = self.calc._compute_expected(
            meter,
            date(2026, 4, 30),
            {"total": 7262, "on_peak": 4943, "off_peak": 2319, "demand_kw": 33},
        )
        # energy = 4943*4.33 + 2319*2.64 ≈ 21,403.2 + 6,122.2 ≈ 27,525.4
        # demand = 33*210 = 6,930
        # service 312.24, Ft = 7262*0.0972 = 705.87
        # subtotal ≈ 35,473 → total ≈ 37,957 (±0.1% vs actual 37,947.33)
        self.assertAlmostEqual(result["total"], 37947.33, delta=200)
        self.assertAlmostEqual(result["energy"], 27516.68, delta=20)
        self.assertAlmostEqual(result["ft"], 705.87, places=1)
        self.assertAlmostEqual(result["demand"], 6930.0, places=1)
        self.assertEqual(result["ft_rate_satang"], 9.72)

    def test_tou_zero_kwh(self):
        meter = self.env["mea.meter"].new({"tariff_id": self.tariff_tou.id})
        result = self.calc._compute_expected(
            meter, date(2026, 4, 1),
            {"total": 0, "on_peak": 0, "off_peak": 0, "demand_kw": 0}
        )
        # zero usage still pays service charge + VAT, no demand
        self.assertEqual(result["energy"], 0)
        self.assertEqual(result["service"], 312.24)
        self.assertEqual(result["ft"], 0)
        self.assertEqual(result["demand"], 0)
        self.assertAlmostEqual(result["total"], 312.24 * 1.07, places=2)

    # -------------- Flat 2.1.2 --------------
    def test_flat_progressive_btv_110_3_march(self):
        """BTV 110/3 March 2026: 1101 kWh, actual energy 4,642.32."""
        meter = self.env["mea.meter"].new({"tariff_id": self.tariff_flat.id})
        result = self.calc._compute_expected(
            meter, date(2026, 3, 1), {"total": 1101}
        )
        # Tier 1: 150 × 3.2484 = 487.26
        # Tier 2: 250 × 4.2218 = 1055.45
        # Tier 3: 701 × 4.4217 = 3099.61
        # Total energy ≈ 4642.32
        self.assertAlmostEqual(result["energy"], 4642.32, places=1)

    def test_flat_below_first_tier(self):
        meter = self.env["mea.meter"].new({"tariff_id": self.tariff_flat.id})
        result = self.calc._compute_expected(
            meter, date(2026, 3, 1), {"total": 100}
        )
        # 100 × 3.2484 = 324.84
        self.assertAlmostEqual(result["energy"], 324.84, places=2)

    # -------------- VAT --------------
    def test_vat_applied(self):
        meter = self.env["mea.meter"].new({"tariff_id": self.tariff_flat.id})
        result = self.calc._compute_expected(
            meter, date(2026, 3, 1), {"total": 100}
        )
        # subtotal = energy + service + Ft
        # vat = subtotal * 0.07
        self.assertAlmostEqual(result["vat"], result["subtotal"] * 0.07, places=4)
        self.assertAlmostEqual(
            result["total"], result["subtotal"] + result["vat"], places=4
        )
