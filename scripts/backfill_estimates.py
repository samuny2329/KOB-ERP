"""Backfill estimated on-peak/off-peak/demand for TOU bills with only kwh_total.

Uses empirical pattern from KOB-KK16 historical bills:
- on/off split ≈ 70/30
- demand kW ≈ on_peak_kwh / 150 (load factor ~80%, 8h × 22 days)

Marks affected records with [estimated] prefix in note field for transparency.
"""
H = env["mea.bill.history"]  # noqa: F821

recs = H.search([("is_tou", "=", True), ("kwh_total", ">", 0),
                 ("kwh_on_peak", "=", 0), ("kwh_off_peak", "=", 0)])
print(f"Backfilling {len(recs)} TOU records...")

for r in recs:
    on_peak = r.kwh_total * 0.70
    off_peak = r.kwh_total * 0.30
    demand_kw = on_peak / 150.0
    note_prefix = "[estimated split 70/30] "
    r.write({
        "kwh_on_peak": round(on_peak, 2),
        "kwh_off_peak": round(off_peak, 2),
        "demand_on_peak": round(demand_kw, 2),
        "note": note_prefix + (r.note or ""),
    })

# Force recompute
all_recs = H.search([])
all_recs._compute_expected()
all_recs._compute_variance()
env.cr.commit()  # noqa: F821

print(f"Done. Total records={len(all_recs)} anomalies={all_recs.filtered('is_anomaly').ids and len(all_recs.filtered('is_anomaly')) or 0}")

# Print Apr 2026 summary
for r in H.search([("billing_month", "=", "2026-04-01")]).sorted("site_short"):
    print(f"  {r.site_short:<14} kwh={r.kwh_total:>7.0f} on={r.kwh_on_peak:>7.0f} off={r.kwh_off_peak:>7.0f} demand={r.demand_on_peak:>5.0f} actual={r.total_amount:>10.2f} expected={r.expected_amount:>10.2f} var={r.variance_pct:>6.1f}%")
