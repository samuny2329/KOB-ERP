# -*- coding: utf-8 -*-
"""Tests for throughput linkage on mea.bill.history.

Validates compute behavior using KK-16 actuals (Apr 2026):
    kwh_total      = 7,262
    total_amount   = 37,947.33
    demand_on_peak = 33 kW
    BTV-WH2 qty    = ~38,000  (sample)
    KOB-WH2 qty    = ~68,634  (sample, makes 106,634 total)
"""
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("kob_mea_billing", "kob_mea_throughput")
class TestThroughputMetrics(TransactionCase):

    def setUp(self):
        super().setUp()
        self.tariff = self.env.ref("kob_mea_billing.tariff_3_2_3")
        self.meter = self.env["mea.meter"].create({
            "ca_number": "099999991",
            "meter_id": "99999991",
            "site_short": "TEST-KK16",
            "tariff_id": self.tariff.id,
        })

    def _bill(self, **overrides):
        vals = {
            "meter_id": self.meter.id,
            "billing_month": date(2026, 4, 1),
            "kwh_total": 7262.0,
            "kwh_on_peak": 4943.0,
            "kwh_off_peak": 2319.0,
            "demand_on_peak": 33.0,
            "total_amount": 37947.33,
        }
        vals.update(overrides)
        return self.env["mea.bill.history"].create(vals)

    def test_qty_total_sums_btv_and_kob(self):
        bill = self._bill(order_qty_btv_wh2=38000, order_qty_kob_wh2=68634)
        self.assertEqual(bill.order_qty_total, 106634)

    def test_kwh_per_order(self):
        bill = self._bill(order_qty_btv_wh2=38000, order_qty_kob_wh2=68634)
        # 7262 / 106634 = 0.0681 (4 dp)
        self.assertAlmostEqual(bill.kwh_per_order, 0.0681, places=4)

    def test_cost_per_order(self):
        bill = self._bill(order_qty_btv_wh2=38000, order_qty_kob_wh2=68634)
        # 37947.33 / 106634 = 0.3559 (4 dp)
        self.assertAlmostEqual(bill.cost_per_order, 0.3559, places=4)

    def test_demand_per_kqty(self):
        bill = self._bill(order_qty_btv_wh2=38000, order_qty_kob_wh2=68634)
        # 33 / (106634/1000) = 33 / 106.634 = 0.3094
        self.assertAlmostEqual(bill.demand_per_kqty, 0.3094, places=4)

    def test_zero_qty_safe(self):
        bill = self._bill(order_qty_btv_wh2=0, order_qty_kob_wh2=0)
        self.assertEqual(bill.order_qty_total, 0)
        self.assertEqual(bill.kwh_per_order, 0.0)
        self.assertEqual(bill.cost_per_order, 0.0)
        self.assertEqual(bill.demand_per_kqty, 0.0)

    def test_recompute_on_qty_change(self):
        bill = self._bill(order_qty_btv_wh2=10000, order_qty_kob_wh2=10000)
        first_kwh_per = bill.kwh_per_order
        bill.order_qty_kob_wh2 = 90000
        # Should recompute: 7262 / 100000 = 0.07262
        self.assertNotEqual(bill.kwh_per_order, first_kwh_per)
        self.assertAlmostEqual(bill.kwh_per_order, 0.07262, places=4)

    # -------------- OT metrics --------------
    def test_ot_kwh_uses_off_peak_when_available(self):
        bill = self._bill(ot_hours_online=1054.7)
        # 2319 / 1054.7 = 2.1987
        self.assertAlmostEqual(bill.kwh_per_ot_hour, 2.1987, places=3)

    def test_ot_kwh_falls_back_to_total_when_off_peak_zero(self):
        bill = self._bill(ot_hours_online=1054.7, kwh_off_peak=0.0)
        # 7262 / 1054.7 = 6.8852
        self.assertAlmostEqual(bill.kwh_per_ot_hour, 6.8852, places=3)

    def test_ot_cost_per_hour(self):
        bill = self._bill(ot_hours_online=1054.7)
        # 37947.33 / 1054.7 = 35.97
        self.assertAlmostEqual(bill.cost_per_ot_hour, 35.9745, places=3)

    def test_ot_orders_per_hour(self):
        bill = self._bill(
            ot_hours_online=1054.7,
            order_qty_btv_wh2=38000, order_qty_kob_wh2=68634,
        )
        # 106634 / 1054.7 = 101.1
        self.assertAlmostEqual(bill.orders_per_ot_hour, 101.1054, places=2)

    def test_ot_zero_hours_safe(self):
        bill = self._bill(ot_hours_online=0.0)
        self.assertEqual(bill.kwh_per_ot_hour, 0.0)
        self.assertEqual(bill.cost_per_ot_hour, 0.0)
        self.assertEqual(bill.orders_per_ot_hour, 0.0)
