"""Seed KOB-specific CRM lost reasons + add lost_reason on sale.order."""
env = self.env  # noqa: F821

KOB_REASONS = [
    "Price too high",
    "Competitor won",
    "No budget",
    "Wrong product fit",
    "Lead unresponsive (ghost)",
    "Out of geographic scope",
    "Customer chose in-house",
    "Bad customer review history",
    "Lost on delivery time",
    "Quality concerns raised",
    "Volume too small for KOB",
    "Customer postponed indefinitely",
]

created = 0
for r in KOB_REASONS:
    existing = env["crm.lost.reason"].search([("name", "=", r)], limit=1)
    if not existing:
        env["crm.lost.reason"].create({"name": r, "active": True})
        created += 1
        print(f"  ✓ {r}")

env.cr.commit()
print(f"\n✓ {created} new lost reasons added (total {env['crm.lost.reason'].search_count([])})")
