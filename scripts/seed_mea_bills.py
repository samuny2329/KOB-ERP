"""Seed mea.bill.history records for all 6 meters × 12 months.

Run via:
  docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d kobdb --no-http < seed_mea_bills.py
"""
from datetime import date


def _d(y, m):
    return date(y, m, 1)


# (ca_number, billing_month, kwh_total, kwh_on_peak, kwh_off_peak,
#  demand_on_peak, total_amount)  on_peak/off_peak/demand may be None
DATA = [
    # ---------- KOB-KK2 (TOU 3.2.3) ----------
    ("015634979", _d(2026, 4), 9868, 7311, 2557, None, 53230.79),
    ("015634979", _d(2026, 3), 10843, 7751, 3092, None, 57104.80),
    ("015634979", _d(2026, 2), 8908, None, None, None, 48704.91),
    ("015634979", _d(2026, 1), 7297, None, None, None, 41446.89),
    ("015634979", _d(2025, 12), 8837, None, None, None, 48437.74),
    ("015634979", _d(2025, 11), 7214, None, None, None, 41270.64),
    ("015634979", _d(2025, 10), 8743, None, None, None, 48850.53),
    ("015634979", _d(2025, 9), 9023, None, None, None, 49736.45),
    ("015634979", _d(2025, 8), 7896, None, None, None, 45180.20),
    ("015634979", _d(2025, 7), 8915, None, None, None, 48902.36),
    ("015634979", _d(2025, 6), 9332, None, None, None, 52112.43),
    ("015634979", _d(2025, 5), 8776, None, None, None, 49087.82),

    # ---------- KOB-KK16 (TOU 3.2.3) ----------
    ("018025585", _d(2026, 4), 7262, 4943, 2319, 33, 37947.33),
    ("018025585", _d(2026, 3), 7235, None, None, None, 37645.45),
    # Pre-Mar 2026: meter+CA owned by ULVAC; readings from MEA bills attached
    # to ULVAC reimburse invoices. We log the kWh under KOB's meter record so
    # 12-month history is contiguous.
    ("018025585", _d(2026, 2), 5891, 4263, 1628, 30, 31586.34),
    ("018025585", _d(2026, 1), 4625, 3291, 1334, 25, 25442.94),
    ("018025585", _d(2025, 12), 5177, 3724, 1453, 28, 28848.57),
    ("018025585", _d(2025, 11), 1301, 842, 459, 25, 11366.30),
    ("018025585", _d(2025, 10), 1920, 1247, 673, 22, 13276.38),

    # ---------- KOB-HQ Floor 32 (Flat 2.1.2) ----------
    ("016315726", _d(2026, 4), 4836, None, None, None, 23176.97),
    ("016315726", _d(2026, 3), 5900, None, None, None, 28321.65),
    ("016315726", _d(2026, 2), 5491, None, None, None, 26344.04),
    ("016315726", _d(2026, 1), 5111, None, None, None, 24506.66),
    ("016315726", _d(2025, 12), 3791, None, None, None, 18367.55),
    ("016315726", _d(2025, 11), 4795, None, None, None, 23286.56),
    ("016315726", _d(2025, 10), 4936, None, None, None, 23977.38),
    ("016315726", _d(2025, 9), 4848, None, None, None, 23546.24),
    ("016315726", _d(2025, 8), 6041, None, None, None, 29649.81),
    ("016315726", _d(2025, 7), 5387, None, None, None, 26417.59),
    ("016315726", _d(2025, 6), 5996, None, None, None, 29427.40),
    ("016315726", _d(2025, 5), 5262, None, None, None, 25799.82),

    # ---------- BTV-110/3 (Flat 2.1.2) ----------
    ("015980029", _d(2026, 4), 1066, None, None, None, 4948.18),
    ("015980029", _d(2026, 3), 1101, None, None, None, 5117.41),
    ("015980029", _d(2026, 2), 1265, None, None, None, 5910.39),
    ("015980029", _d(2026, 1), 1322, None, None, None, 6186.00),
    ("015980029", _d(2025, 12), 1149, None, None, None, 5423.26),
    ("015980029", _d(2025, 11), 875, None, None, None, 4080.83),
    ("015980029", _d(2025, 10), 1039, None, None, None, 4884.34),
    ("015980029", _d(2025, 9), 1132, None, None, None, 5339.97),
    ("015980029", _d(2025, 8), 1126, None, None, None, 5358.77),
    ("015980029", _d(2025, 7), 1116, None, None, None, 5309.36),
    ("015980029", _d(2025, 6), 581, None, None, None, 2665.26),
    ("015980029", _d(2025, 5), 728, None, None, None, 3391.77),

    # ---------- BTV-24/8 (Flat 2.1.2) ----------
    ("016470419", _d(2026, 4), 2580, None, None, None, 12268.72),
    ("016470419", _d(2026, 3), 2281, None, None, None, 10822.98),
    ("016470419", _d(2026, 2), 2254, None, None, None, 10692.42),
    ("016470419", _d(2026, 1), 2344, None, None, None, 11127.59),
    ("016470419", _d(2025, 12), 1598, None, None, None, 7623.12),
    ("016470419", _d(2025, 11), 2684, None, None, None, 12943.88),
    ("016470419", _d(2025, 10), 4023, None, None, None, 19504.22),
    ("016470419", _d(2025, 9), 4142, None, None, None, 20087.24),
    ("016470419", _d(2025, 8), 4686, None, None, None, 22953.09),
    ("016470419", _d(2025, 7), 4175, None, None, None, 20427.62),
    ("016470419", _d(2025, 6), 4192, None, None, None, 20511.63),
    ("016470419", _d(2025, 5), 4417, None, None, None, 21623.63),

    # ---------- CMN-Tower (TOU 3.2.3 assumed) ----------
    ("014953128", _d(2026, 4), 29986, None, None, None, 186253.57),
    ("014953128", _d(2026, 3), 34225, None, None, None, 202484.71),
    ("014953128", _d(2026, 2), 30355, None, None, None, 188545.86),
    ("014953128", _d(2026, 1), 33251, None, None, None, 198116.82),
    ("014953128", _d(2025, 12), 30221, None, None, None, 187607.52),
    ("014953128", _d(2025, 11), 33421, None, None, None, 195665.42),
    ("014953128", _d(2025, 10), 38639, None, None, None, 221480.91),
    ("014953128", _d(2025, 9), 40057, None, None, None, 232968.66),
    ("014953128", _d(2025, 8), 41682, None, None, None, 241254.54),
    ("014953128", _d(2025, 7), 36222, None, None, None, 212322.52),
    ("014953128", _d(2025, 6), 38485, None, None, None, 217438.15),
    ("014953128", _d(2025, 5), 33595, None, None, None, 192125.24),
]


def run(env):
    Meter = env["mea.meter"]
    Hist = env["mea.bill.history"]
    Ft = env["mea.ft.period"]

    created = updated = skipped = 0
    by_meter = {}

    for ca, month, kwh, on_peak, off_peak, demand, total in DATA:
        meter = Meter.search([("ca_number", "=", ca)], limit=1)
        if not meter:
            print(f"⚠ no meter for CA {ca}, skipping {month}")
            skipped += 1
            continue

        ft_period = Ft.get_for_date(month)
        ft_rate = ft_period.ft_rate / 100.0 if ft_period else 0.0

        vals = {
            "meter_id": meter.id,
            "billing_month": month,
            "kwh_total": kwh,
            "kwh_on_peak": on_peak or 0.0,
            "kwh_off_peak": off_peak or 0.0,
            "demand_on_peak": demand or 0.0,
            "ft_rate": ft_rate,
            "total_amount": total,
            "source": "manual",
            "extraction_confidence": 1.0,
            "state": "confirmed",
            "note": "Seeded from MEA portal + ULVAC reimburse PDFs (May 2025 – Apr 2026).",
        }

        existing = Hist.search([
            ("meter_id", "=", meter.id),
            ("billing_month", "=", month),
        ], limit=1)
        if existing:
            existing.write(vals)
            updated += 1
            by_meter.setdefault(meter.site_short, [0, 0])[1] += 1
        else:
            Hist.create(vals)
            created += 1
            by_meter.setdefault(meter.site_short, [0, 0])[0] += 1

    env.cr.commit()
    print(f"\n✅ created={created}  updated={updated}  skipped={skipped}")
    print("Per meter (created / updated):")
    for site, (c, u) in sorted(by_meter.items()):
        print(f"  {site:<14} {c} / {u}")


run(env)  # noqa: F821 — `env` provided by Odoo shell
