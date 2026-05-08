"""Backfill demand_on_peak when on_peak is known but demand=0."""
H = env["mea.bill.history"]  # noqa: F821

recs = H.search([("is_tou", "=", True), ("kwh_on_peak", ">", 0),
                 ("demand_on_peak", "=", 0)])
print(f"Backfilling demand on {len(recs)} records...")

for r in recs:
    demand_kw = r.kwh_on_peak / 150.0
    is_estimated = "[estimated demand]" not in (r.note or "")
    new_note = ("[estimated demand] " if is_estimated else "") + (r.note or "")
    r.write({
        "demand_on_peak": round(demand_kw, 2),
        "note": new_note,
    })

H.search([])._compute_expected()
H.search([])._compute_variance()
env.cr.commit()  # noqa: F821
print("Done.")

for r in H.search([("billing_month", "=", "2026-04-01")]).sorted("site_short"):
    print(f"  {r.site_short:<14} on={r.kwh_on_peak:>7.0f} off={r.kwh_off_peak:>7.0f} demand={r.demand_on_peak:>6.1f} actual={r.total_amount:>10.2f} expected={r.expected_amount:>10.2f}")
