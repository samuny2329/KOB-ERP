#!/usr/bin/env python3
"""Create core VAT taxes on BTV (co 2) + CMN (co 4) — minimal repartition lines.

Avoids copying from co1 because repartition.line.account_id refers to
company-1 chart of accounts.
"""

env = self.env  # noqa: F821

TH = env["res.country"].search([("code", "=", "TH")], limit=1)
print(f"Thailand id: {TH.id}")

# Use existing tax_group ids
vat7_group = env["account.tax.group"].search(
    [("name", "ilike", "VAT 7")], limit=1,
)
print(f"VAT 7% group: {vat7_group.id}")

# Definitions
TAXES = [
    # (name, type_tax_use, amount, description)
    ("7% Input VAT",            "purchase", 7.0, "Input VAT 7%"),
    ("7% Output VAT",           "sale",     7.0, "Output VAT 7%"),
    ("0%",                      "purchase", 0.0, "Input VAT 0%"),
    ("0%",                      "sale",     0.0, "Output VAT 0%"),
    ("0% EXEMPT",               "purchase", 0.0, "Input VAT Exempted"),
    ("0% EXEMPT",               "sale",     0.0, "Output VAT Exempted"),
    ("Suspense Input Tax 7%",   "purchase", 7.0, "Pending VAT input"),
    ("Suspense Output Tax 7%",  "sale",     7.0, "Pending VAT output"),
    ("PP 36",                   "purchase", 0.0, "Reverse-charge VAT (foreign service)"),
]

created = 0
skipped = 0

for cid in [2, 4]:
    company = env["res.company"].browse(cid)
    print(f"\n→ Company {cid} ({company.name})")
    for name, ttype, amt, desc in TAXES:
        existing = env["account.tax"].search([
            ("company_id", "=", cid),
            ("name", "=", name),
            ("type_tax_use", "=", ttype),
        ], limit=1)
        if existing:
            skipped += 1
            continue
        try:
            new_tax = env["account.tax"].with_context(
                default_company_id=cid,
            ).create({
                "name": name,
                "amount": float(amt),
                "amount_type": "percent",
                "type_tax_use": ttype,
                "company_id": cid,
                "country_id": TH.id,
                "tax_group_id": vat7_group.id,
                "description": desc,
                "active": True,
            })
            created += 1
            print(f"  ✓ #{new_tax.id} {name} ({ttype})")
        except Exception as e:
            print(f"  ! {name} ({ttype}): {e!r}"[:140])

env.cr.commit()
print(f"\nSummary: {created} created, {skipped} skipped")

# Final check
print("\n=== Tax counts per company ===")
for cid in [1, 2, 4]:
    co = env["res.company"].browse(cid)
    n = env["account.tax"].search_count([("company_id", "=", cid)])
    print(f"  co{cid} {co.name}: {n} taxes")
