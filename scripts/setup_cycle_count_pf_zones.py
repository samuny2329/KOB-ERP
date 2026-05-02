#!/usr/bin/env python3
"""Create cycle-count rules per PF zone (PF-A through PF-G).

OCA stock_cycle_count rule_type options:
  - 'periodic'       — every N days
  - 'turnover'       — based on inventory value movement
  - 'zero'           — when location goes empty
  - 'accuracy'       — when discrepancy threshold exceeded
"""

env = self.env  # noqa: F821

KON_WH = env["stock.warehouse"].search([("code", "=", "K-On")], limit=1)
print(f"K-On warehouse id: {KON_WH.id}")

ZONES = [
    # (zone_letter, count_period_days, qty_per_period)
    ("A", 30, 10),   # high-velocity zone — count 10 bins/month
    ("B", 30, 10),
    ("C", 30, 10),
    ("D", 60, 8),    # mid-velocity
    ("E", 60, 8),
    ("F", 90, 5),    # slow-moving
    ("G", 90, 5),
]

created = 0
for zone_letter, period_days, qty_per_period in ZONES:
    rule_name = f"PF-{zone_letter} Periodic Count ({period_days}d)"
    existing = env["stock.cycle.count.rule"].search(
        [("name", "=", rule_name)], limit=1,
    )
    if existing:
        # Re-link locations
        zone_bins = env["stock.location"].search([
            ("complete_name", "=like", f"K-On/Stock/PICKFACE/PF-{zone_letter}-%"),
        ])
        for loc in zone_bins:
            env.cr.execute(
                "INSERT INTO location_cycle_count_rule_rel "
                "(rule_id, location_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (existing.id, loc.id),
            )
        print(f"  · {rule_name} re-linked to {len(zone_bins)} bins")
        continue
    try:
        rule = env["stock.cycle.count.rule"].create({
            "name": rule_name,
            "rule_type": "periodic",
            "periodic_count_period": period_days,
            "periodic_qty_per_period": qty_per_period,
            "apply_in": "warehouse",
            "active": True,
        })
        # Attach rule to K-On warehouse via M2M
        env.cr.execute(
            "INSERT INTO warehouse_cycle_count_rule_rel (rule_id, warehouse_id) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (rule.id, KON_WH.id),
        )
        # Attach to all locations matching this zone (under PICKFACE 4-level)
        zone_bins = env["stock.location"].search([
            ("complete_name", "=like", f"K-On/Stock/PICKFACE/PF-{zone_letter}-%"),
        ])
        if zone_bins:
            for loc in zone_bins:
                env.cr.execute(
                    "INSERT INTO location_cycle_count_rule_rel "
                    "(rule_id, location_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (rule.id, loc.id),
                )
        print(f"  ✓ {rule_name} | applied to {len(zone_bins)} bins")
        created += 1
    except Exception as e:
        print(f"  ! {rule_name} failed: {e!r}"[:120])

env.cr.commit()
print(f"\n✓ {created} cycle-count rules created")

# Final verification
print("\n=== Cycle Count Rules ===")
for r in env["stock.cycle.count.rule"].search([], order="name"):
    print(f"  #{r.id:3d} | {r.name} | type={r.rule_type} | "
          f"period={r.periodic_count_period}d | qty={r.periodic_qty_per_period}")
