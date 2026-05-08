"""Force recompute of expected_amount on all bill records."""
H = env["mea.bill.history"]  # noqa: F821
recs = H.search([])
print(f"Force-recomputing {len(recs)} records...")
recs._compute_expected()
recs._compute_variance()
env.cr.commit()  # noqa: F821

anomalies = H.search_count([("is_anomaly", "=", True)])
zero_expected = H.search_count([("expected_amount", "<", 100)])
print(f"Done. anomalies={anomalies} zero_expected={zero_expected}")

# Sample print
for r in H.search([("billing_month", "=", "2026-04-01")]):
    print(f"  {r.site_short:<14} kwh={r.kwh_total:>7.0f} actual={r.total_amount:>10.2f} expected={r.expected_amount:>10.2f} var={r.variance_pct:>6.1f}%")
