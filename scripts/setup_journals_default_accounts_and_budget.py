env = self.env  # noqa: F821

# ─── 1. Wire missing default accounts on general journals ─────────
print("Step 1: Wire default_account_id on general-type journals")
ASSIGN = {
    "MISC": "999900",   # Suspense Misc fallback (use existing 101299 Bank Suspense)
    "EXCH": "510302",   # Realized FX Gain/Loss
    "JV":   "999900",   # Journal Voucher uses misc clearing
    "CABA": "213100",   # Cash Basis Tax → Undue Output VAT
    "STJ":  "101407",   # Inventory Valuation → Goods In Transit
}

# Find best-matching account by code prefix
def find_account(code_pref, company_id):
    return env["account.account"].search([
        ("code_store", "ilike", code_pref),
        ("company_ids", "in", company_id),
    ], limit=1)

for jcode, acc_code in ASSIGN.items():
    j = env["account.journal"].search(
        [("code", "=", jcode), ("company_id", "=", 1)], limit=1,
    )
    if not j:
        print(f"  · {jcode}: journal not found, skip")
        continue
    if j.default_account_id:
        print(f"  · {jcode}: already set ({(j.default_account_id.code or '?') if j.default_account_id else '?'})")
        continue
    a = find_account(acc_code, 1)
    if not a:
        # Fallback: first asset_current
        a = env["account.account"].search([
            ("account_type", "=", "asset_current"),
            ("company_ids", "in", 1),
        ], limit=1)
    if a:
        j.default_account_id = a.id
        print(f"  ✓ {jcode} → {(a.code or '?')} {a.name}")

env.cr.commit()

# ─── 2. Sample Budget templates (CapEx + OpEx) ────────────────────
print("\nStep 2: Create sample CapEx + OpEx budget templates for FY2026")

YEAR = 2026
TEMPLATES = [
    # CapEx
    ("CAPEX-FY26-Equipment",     "capex", "capex_equipment", 500_000),
    ("CAPEX-FY26-IT Hardware",   "capex", "capex_it",         300_000),
    ("CAPEX-FY26-Software",      "capex", "capex_software",   200_000),
    ("CAPEX-FY26-Office Improv", "capex", "capex_building",   400_000),
    ("CAPEX-FY26-Vehicle",       "capex", "capex_vehicle",    600_000),
    # OpEx
    ("OPEX-FY26-Marketing",      "opex",  "opex_marketing",  2_000_000),
    ("OPEX-FY26-Salaries",       "opex",  "opex_salaries",  10_000_000),
    ("OPEX-FY26-Rent",           "opex",  "opex_rent",         800_000),
    ("OPEX-FY26-Subscriptions",  "opex",  "opex_subscription", 360_000),
    ("OPEX-FY26-Travel",         "opex",  "opex_travel",       240_000),
    ("OPEX-FY26-Training",       "opex",  "opex_training",     150_000),
    ("OPEX-FY26-Maintenance",    "opex",  "opex_maintenance",  180_000),
    ("OPEX-FY26-Supplies",       "opex",  "opex_supplies",     120_000),
    ("OPEX-FY26-Professional",   "opex",  "opex_professional", 500_000),
]

created = 0
for name, etype, cat, amount in TEMPLATES:
    existing = env["kob.procurement.budget"].search(
        [("name", "=", name)], limit=1,
    )
    if existing:
        print(f"  · {name}: already exists")
        continue
    try:
        env["kob.procurement.budget"].create({
            "name": name,
            "fiscal_year": YEAR,
            "period_from": f"{YEAR}-01-01",
            "period_to": f"{YEAR}-12-31",
            "expenditure_type": etype,
            "category": cat,
            "total_budget": amount,
            "company_id": 1,
            "state": "active",
            "auto_block_overrun": True,
        })
        print(f"  ✓ {name:35s} {amount:>14,} ฿  ({etype.upper()}/{cat})")
        created += 1
    except Exception as e:
        print(f"  ! {name}: {e!r}"[:120])

env.cr.commit()
print(f"\n✓ {created} budget records created")

# ─── 3. Summary ──────────────────────────────────────────────────
print("\n=== Final state ===")
print("\nJournal default accounts (KOB co1):")
for j in env["account.journal"].search([("company_id", "=", 1)], order="type, code"):
    code = (j.default_account_id.code or "—") if j.default_account_id else "—"
    print(f"  {j.code:7s} {j.type:9s} → {code}")

print("\nBudget summary (FY2026, KOB):")
totals = {"capex": 0, "opex": 0}
for b in env["kob.procurement.budget"].search(
    [("fiscal_year", "=", YEAR), ("company_id", "=", 1), ("state", "=", "active")],
):
    totals[b.expenditure_type or "opex"] += float(b.total_budget or 0)
print(f"  CapEx total: {totals['capex']:>14,.0f} ฿")
print(f"  OpEx total:  {totals['opex']:>14,.0f} ฿")
print(f"  GRAND TOTAL: {sum(totals.values()):>14,.0f} ฿")
