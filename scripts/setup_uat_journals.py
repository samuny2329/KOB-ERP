#!/usr/bin/env python3
"""Create UAT-style accounting dashboard journals for company 1 (KOB).

Mirrors:
  - Customer Invoices, Vendor Bills (already exist on co1)
  - Journal Voucher (general)
  - Advance payment-Others (bank → 101707)
  - LC / TR : KOB : SCB 12M LC/TR 150 Days (bank → 213050 new liability)
  - Suspense Account (bank → 101299)
  - 6 bank journals (101201-101204, 101251-101252)

Run via:
  docker exec -i kob-odoo-19 odoo shell -d kobdb --no-http < scripts/setup_uat_journals.py
"""

env = self.env  # noqa: F821 — provided by odoo shell

COMPANY_ID = 1  # KOB
company = env["res.company"].browse(COMPANY_ID)
print(f"Setting up dashboard journals for: {company.name}")

# ----- 1. Create LC/TR liability account if missing -----
LC_CODE = "213050"
lc_acc = env["account.account"].search(
    [("code_store", "ilike", LC_CODE)], limit=1,
)
if not lc_acc:
    lc_acc = env["account.account"].create({
        "code": LC_CODE,
        "name": "LC/TR — Letter of Credit / Trust Receipt",
        "account_type": "liability_current",
        "company_ids": [(4, COMPANY_ID)],
        "reconcile": True,
    })
    print(f"  ✓ Created LC/TR account {LC_CODE}")
else:
    print(f"  · LC/TR account already exists: {lc_acc.id}")

# ----- 2. Helper to get account by code on co1 -----
def acc(code):
    a = env["account.account"].search(
        [("code_store", "ilike", code), ("company_ids", "in", COMPANY_ID)],
        limit=1,
    )
    if not a:
        # try without company filter
        a = env["account.account"].search(
            [("code_store", "ilike", code)], limit=1,
        )
    return a

# ----- 3. Journal definitions matching UAT layout -----
JOURNALS = [
    # (name,           code,    type,     default_acc_code, suspense_acc_code,  show)
    ("KOB SA SCB 0782365093",   "101201", "bank",    "101201", "101299", True),
    ("KOB SA KBANK 7702240659", "101202", "bank",    "101202", "101299", True),
    ("KOB SA BAY 4741107803",   "101203", "bank",    "101203", "101299", True),
    ("KOB SA BBL 0630403848",   "101204", "bank",    "101204", "101299", True),
    ("KOB CA SCB 0783022680",   "101251", "bank",    "101251", "101299", True),
    ("KOB CA KBANK 7701003556", "101252", "bank",    "101252", "101299", True),
    ("Advance payment-Others",  "ADVOTH", "bank",    "101707", "101299", True),
    ("LC / TR : KOB : SCB 12M LC/TR 150 Days", "LCTR", "bank", "213050", "101299", True),
    ("Suspense Account",        "SUSP",   "general", "101299", None,     True),
    ("Journal Voucher",         "JV",     "general", None,     None,     True),
]

created = 0
updated = 0
for name, code, jtype, def_code, susp_code, show in JOURNALS:
    j = env["account.journal"].search(
        [("code", "=", code), ("company_id", "=", COMPANY_ID)],
        limit=1,
    )
    vals = {
        "name": name,
        "code": code,
        "type": jtype,
        "company_id": COMPANY_ID,
        "show_on_dashboard": show,
    }
    if def_code:
        a = acc(def_code)
        if a:
            vals["default_account_id"] = a.id
    if susp_code:
        a = acc(susp_code)
        if a:
            vals["suspense_account_id"] = a.id
    if not j:
        j = env["account.journal"].create(vals)
        print(f"  ✓ Created journal {code:8s} | {name}")
        created += 1
    else:
        j.write(vals)
        print(f"  · Updated journal {code:8s} | {name}")
        updated += 1

env.cr.commit()
print(f"\nSummary: {created} created, {updated} updated")
print("Dashboard tiles refresh on next page reload.")
