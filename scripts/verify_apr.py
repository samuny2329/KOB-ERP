"""Verify Apr 2026 records exist for all 6 meters."""
H = env["mea.bill.history"]  # noqa: F821
recs = H.search([("billing_month", "=", "2026-04-01")]).sorted("site_short")
print(f"Apr 2026 records: {len(recs)}")
for r in recs:
    print(f"  id={r.id} site={r.site_short:<14} kwh={r.kwh_total:>7.0f} actual={r.total_amount:>10.2f} expected={r.expected_amount:>10.2f}")
