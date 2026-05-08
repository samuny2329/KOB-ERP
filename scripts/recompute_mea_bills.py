"""Recompute expected_amount + variance on all mea.bill.history records."""
H = env["mea.bill.history"]  # noqa: F821
recs = H.search([])
print(f"Recomputing {len(recs)} bill records...")
recs.invalidate_recordset(["expected_amount", "expected_breakdown",
                           "variance", "variance_pct", "is_anomaly"])
# Force recompute by reading
for r in recs:
    _ = r.expected_amount
env.cr.commit()  # noqa: F821
anomalies = H.search_count([("is_anomaly", "=", True)])
print(f"Done. anomalies={anomalies}/{len(recs)}")
