#!/usr/bin/env python3
"""Rename KOB taxes to match UAT + clone for BTV/CMN + add Suspense/PP36."""

env = self.env  # noqa: F821

COMPANIES = [1, 2, 4]  # KOB, BTV, CMN

# Step 1: rename core VAT taxes on KOB to match UAT exactly
RENAMES = [
    # (existing local id, new name, new description)
    (1, "7% Input VAT",  "Input VAT 7%"),
    (2, "7% Output VAT", "Output VAT 7%"),
    (3, "0%",            "Input VAT 0%"),
    (4, "0%",            "Output VAT 0%"),
    (5, "0% EXEMPT",     "Input VAT Exempted"),
    (6, "0% EXEMPT",     "Output VAT Exempted"),
]

for tid, name, desc in RENAMES:
    t = env["account.tax"].browse(tid)
    if t.exists():
        t.with_context(lang="en_US").name = name
        t.description = desc
        print(f"  · #{tid:3d} → {name}")

env.cr.commit()

# Step 2: ensure VAT 7% tax_group is consistent (use existing id 5)
vat7_group = env["account.tax.group"].search(
    [("name", "ilike", "VAT 7")], limit=1,
) or env["account.tax.group"].search([], limit=1)

# Step 3: copy core taxes onto BTV (2) and CMN (4)
for cid in [2, 4]:
    company = env["res.company"].browse(cid)
    print(f"\n→ Cloning core taxes to company {cid} ({company.name})")
    for src_id, name, desc in RENAMES:
        existing = env["account.tax"].search([
            ("company_id", "=", cid),
            ("name", "=", name),
            ("type_tax_use", "=", env["account.tax"].browse(src_id).type_tax_use),
            ("amount", "=", env["account.tax"].browse(src_id).amount),
        ], limit=1)
        if existing:
            print(f"    · {name} ({env['account.tax'].browse(src_id).type_tax_use}) exists")
            continue
        src = env["account.tax"].browse(src_id)
        try:
            new_tax = src.copy({
                "company_id": cid,
                "name": name,
                "description": desc,
            })
            print(f"    ✓ Created {name} ({src.type_tax_use}) on co{cid}")
        except Exception as e:
            print(f"    ! Failed {name}: {e!r}"[:120])

env.cr.commit()

# Step 4: Add UAT-specific taxes (Suspense + PP 36) on all 3 companies
EXTRA_TAXES = [
    # (name,                    type_tax_use, amount, description)
    ("Suspense Input Tax 7%",   "purchase",   7.0,    "Pending VAT input"),
    ("Suspense Output Tax 7%",  "sale",       7.0,    "Pending VAT output"),
    ("PP 36",                   "purchase",   0.0,    "Reverse-charge VAT (foreign service)"),
]

for cid in COMPANIES:
    for name, ttype, amt, desc in EXTRA_TAXES:
        existing = env["account.tax"].search([
            ("company_id", "=", cid),
            ("name", "=", name),
            ("type_tax_use", "=", ttype),
        ], limit=1)
        if existing:
            continue
        try:
            env["account.tax"].create({
                "name": name,
                "amount": amt,
                "amount_type": "percent",
                "type_tax_use": ttype,
                "company_id": cid,
                "tax_group_id": vat7_group.id,
                "description": desc,
            })
            print(f"  ✓ co{cid}: {name} ({ttype})")
        except Exception as e:
            print(f"  ! co{cid}: {name} failed: {e!r}"[:120])

env.cr.commit()

# Final verification
print("\n=== After sync ===")
for cid in COMPANIES:
    cnt = env["account.tax"].search_count([("company_id", "=", cid)])
    print(f"  Company {cid}: {cnt} taxes")
print("\nKOB core taxes:")
for t in env["account.tax"].search([
    ("company_id", "=", 1),
    ("name", "in", [r[1] for r in RENAMES] + [e[0] for e in EXTRA_TAXES]),
], order="type_tax_use, amount, name"):
    print(f"  #{t.id:4d} | {t.type_tax_use:8s} | {t.amount:5.2f}% | {t.name}")
