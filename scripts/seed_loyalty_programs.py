"""Seed KOB loyalty programs using sale_loyalty (Community)."""
env = self.env  # noqa: F821

PROGRAMS = [
    {
        "name": "KOB VIP — 10% Welcome",
        "program_type": "promotion",
        "trigger": "auto",
        "applies_on": "current",
        "rules": [{"reward_point_amount": 1.0, "minimum_amount": 1000.0}],
        "rewards": [{"discount": 10, "discount_mode": "percent",
                     "discount_applicability": "order"}],
    },
    {
        "name": "Refer-a-Friend — ฿200 OFF",
        "program_type": "promotion",
        "trigger": "with_code",
        "applies_on": "current",
        "rules": [{"minimum_amount": 500.0}],
        "rewards": [{"discount": 200, "discount_mode": "per_order",
                     "discount_applicability": "order"}],
    },
    {
        "name": "KOB Gold — Buy 2 Get 1 Free (50ml SKUs)",
        "program_type": "promotion",
        "trigger": "auto",
        "applies_on": "current",
        "rules": [{"minimum_qty": 2}],
        "rewards": [{"reward_type": "discount", "discount": 33,
                     "discount_mode": "percent"}],
    },
]

created = 0
for prog in PROGRAMS:
    existing = env["loyalty.program"].search([("name", "=", prog["name"])], limit=1)
    if existing:
        print(f"  · {prog['name']}: exists")
        continue
    rules = prog.pop("rules")
    rewards = prog.pop("rewards")
    try:
        p = env["loyalty.program"].create({
            **prog,
            "rule_ids": [(0, 0, r) for r in rules],
            "reward_ids": [(0, 0, r) for r in rewards],
            "active": True,
        })
        created += 1
        print(f"  ✓ {p.name}")
    except Exception as e:
        print(f"  ! {prog['name']}: {e!r}"[:120])

env.cr.commit()
print(f"\n=== Final ===")
print(f"  Loyalty programs: {env['loyalty.program'].search_count([])}")
