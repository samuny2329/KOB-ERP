#!/usr/bin/env python3
"""Fix bank journal codes — Odoo's code is varchar(5), so 101201/101202 collide.

Use 5-char codes (B201, B202, ..., B252) and put the bank account number into
the journal NAME (which is what shows on the dashboard tile).
"""

env = self.env  # noqa: F821 — provided by odoo shell

COMPANY_ID = 1

# Drop the two junk bank journals created earlier (codes "10120" / "10125")
junk = env["account.journal"].search([
    ("company_id", "=", COMPANY_ID),
    ("code", "in", ["10120", "10125"]),
])
if junk:
    print(f"Removing {len(junk)} truncated-code journals: {junk.mapped('code')}")
    junk.unlink()

# 6 bank journals — name matches UAT layout, code is short & unique.
BANKS = [
    # (name,                            code,    default_acc_code)
    ("101201 KOB SA SCB 0782365093",    "B201", "101201"),
    ("101202 KOB SA KBANK 7702240659",  "B202", "101202"),
    ("101203 KOB SA BAY 4741107803",    "B203", "101203"),
    ("101204 KOB SA BBL 0630403848",    "B204", "101204"),
    ("101251 KOB CA SCB 0783022680",    "B251", "101251"),
    ("101252 KOB CA KBANK 7701003556",  "B252", "101252"),
]

def acc(code):
    return env["account.account"].search(
        [("code_store", "ilike", code)], limit=1,
    )

susp = acc("101299")
created = updated = 0
for name, code, def_code in BANKS:
    j = env["account.journal"].search(
        [("code", "=", code), ("company_id", "=", COMPANY_ID)], limit=1,
    )
    vals = {
        "name": name,
        "code": code,
        "type": "bank",
        "company_id": COMPANY_ID,
        "show_on_dashboard": True,
        "default_account_id": acc(def_code).id,
        "suspense_account_id": susp.id,
    }
    if j:
        j.write(vals)
        updated += 1
        print(f"  · Updated {code}  | {name}")
    else:
        env["account.journal"].create(vals)
        created += 1
        print(f"  ✓ Created {code}  | {name}")

env.cr.commit()
print(f"\nBank journals: {created} created, {updated} updated")

# Final list
print("\nDashboard journals on KOB:")
for j in env["account.journal"].search(
    [("company_id", "=", COMPANY_ID), ("show_on_dashboard", "=", True)],
    order="type, sequence, id",
):
    print(f"  {j.code:6s} {j.type:8s} | {j.name}")
