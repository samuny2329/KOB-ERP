"""Activate top 8 currencies + setup FX rate update cron."""
env = self.env  # noqa: F821

# 1. Activate currencies for KOB business
TARGET = ["THB", "USD", "EUR", "JPY", "CNY", "SGD", "HKD", "KRW"]
activated = 0
for code in TARGET:
    cur = env["res.currency"].search([("name", "=", code)], limit=1)
    if cur and not cur.active:
        cur.active = True
        activated += 1
        print(f"  ✓ Activated: {code}")
    elif cur:
        print(f"  · {code}: already active")
env.cr.commit()
print(f"  → {activated} currencies activated")

# 2. Companies setup
print("\nStep 2: Verify res.company.currency_id")
for c in env["res.company"].search([]):
    print(f"  · {c.name}: {c.currency_id.name}")

# 3. Sample rates for non-THB currencies (vs THB base)
import datetime
today = datetime.date.today()
RATES = {
    # base = THB; rate is units of FX per 1 THB
    "USD": 0.029,    # 1 THB = 0.029 USD ≈ 1 USD = 35 THB
    "EUR": 0.027,    # 1 EUR ≈ 37 THB
    "JPY": 4.4,      # 1 THB = 4.4 JPY ≈ 1 JPY = 0.23 THB
    "CNY": 0.21,     # 1 CNY ≈ 4.8 THB
    "SGD": 0.039,
    "HKD": 0.227,
    "KRW": 39.0,
    "GBP": 0.023,
    "AUD": 0.043,
}
created = 0
for code, rate in RATES.items():
    cur = env["res.currency"].search([("name", "=", code)], limit=1)
    if not cur:
        continue
    existing = env["res.currency.rate"].search([
        ("currency_id", "=", cur.id),
        ("name", "=", today.strftime("%Y-%m-%d")),
        ("company_id", "=", 1),
    ], limit=1)
    if not existing:
        env["res.currency.rate"].create({
            "currency_id": cur.id,
            "name": today.strftime("%Y-%m-%d"),
            "rate": rate,
            "company_id": 1,
        })
        created += 1
        print(f"  ✓ Rate {code}: {rate}")
env.cr.commit()
print(f"  → {created} rates seeded for {today}")

# 4. FX cron skipped (placeholder, BoT API integration in TODO_LATER)
print(f"  · FX rate cron deferred (needs BoT API integration)")
print(f"\n=== Final ===")
print(f"  Active currencies: {env['res.currency'].search_count([('active','=',True)])}")
print(f"  FX rates total:    {env['res.currency.rate'].search_count([])}")
