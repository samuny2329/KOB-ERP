# -*- coding: utf-8 -*-
"""KOB ERP — migrate every login to <Firstname>.<lastInitial>@kissofbeauty.co.th

Run via Odoo shell (preserves ORM context, hooks, history):

    docker exec -i kob-odoo-19 odoo shell \
        -c /etc/odoo/odoo.conf -d kobdb --no-http \
        < scripts/migrate_user_emails.py

Or for local dev (port 8069, no docker):

    python odoo-bin shell -c config/odoo.conf -d kob_erp --no-http \
        < scripts/migrate_user_emails.py

What it does:
    For every res.users that is NOT a system account, derive a new login
    from the linked employee's name (or partner.name as fallback) using
    pattern  <Firstname>.<lastInitialLower>@kissofbeauty.co.th.
    On collision, append .2, .3, ...

    Updates res.users.login + res.users.email + linked partner.email.

    Writes /tmp/kob_login_migration.csv with old→new mapping for audit.
"""
import csv
import re

# ── Config ─────────────────────────────────────────────────────────
DOMAIN = "kissofbeauty.co.th"

# Logins we never touch — system accounts that other code references
# by xmlid or by literal login string.
PROTECTED_LOGINS = {
    "admin",
    "__system__",
    "public",
    "portaltemplate",
    "default",
    "OdooBot",
    "odoobot",
}
PROTECTED_XMLIDS = {
    "base.user_root",
    "base.user_admin",
    "base.public_user",
    "base.default_user",
    "base.partner_root",
    "base.user_demo",
}


def _strip_alnum(s):
    return "".join(c for c in (s or "") if c.isalnum())


def _split_name(name):
    """Return (first, last) from a full name. Skip Mr/Mrs/นาย/นาง prefixes."""
    if not name:
        return "", ""
    parts = re.split(r"\s+", name.strip())
    parts = [p for p in parts if p and not re.match(
        r"^(Mr|Mrs|Ms|Miss|Dr|นาย|นาง|นางสาว|น\.ส\.|ดร\.)\.?$", p, re.I)]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def _ascii_only(s):
    """Keep only ASCII letters/digits — drop Thai/diacritics."""
    return "".join(c for c in (s or "") if c.isascii() and c.isalnum())


def _make_login(first, last):
    """Build <Firstname>.<lastInitialLower> using ASCII characters only."""
    f = _ascii_only(first)
    if f:
        f = f[:1].upper() + f[1:].lower()
    l_init = ""
    for c in last or "":
        if c.isascii() and c.isalpha():
            l_init = c.lower()
            break
    if f and l_init:
        return f"{f}.{l_init}"
    return f or l_init or ""


def _resolve_name(user):
    """Pull the most authoritative EN name we can find for this user.

    Priority: employee_id (current_version_id.name → name) →
              partner_id.name → user.name → user.login.
    """
    emp = None
    try:
        emp = user.employee_id
    except Exception:
        pass
    if emp and getattr(emp, "current_version_id", False):
        v = emp.current_version_id
        for fld in ("private_name", "name", "first_name"):
            val = getattr(v, fld, None)
            if val and any(c.isascii() and c.isalpha() for c in val):
                return val
    if emp and emp.name:
        if any(c.isascii() and c.isalpha() for c in emp.name):
            return emp.name
    p = user.partner_id
    if p and p.name and any(c.isascii() and c.isalpha() for c in p.name):
        return p.name
    return user.name or user.login


# ── Run ────────────────────────────────────────────────────────────
print("[KOB] Starting login migration → @{}".format(DOMAIN))

User = env["res.users"].sudo()
all_users = User.search([("active", "in", [True, False])])
print(f"  Found {len(all_users)} res.users records (active+inactive)")

# Build set of protected user IDs from xmlids
protected_ids = set()
for xid in PROTECTED_XMLIDS:
    rec = env.ref(xid, raise_if_not_found=False)
    if rec:
        protected_ids.add(rec.id)

results = []   # (uid, old_login, new_login, status)
new_login_taken = set()

for u in all_users:
    if u.id in protected_ids or u.login in PROTECTED_LOGINS:
        results.append((u.id, u.login, u.login, "PROTECTED — skip"))
        continue

    full_name = _resolve_name(u)
    first, last = _split_name(full_name)
    base = _make_login(first, last)

    if not base:
        results.append((u.id, u.login, u.login,
                        f"no ASCII name ({full_name!r}) — skip"))
        continue

    # Resolve collisions: <base>.2, .3, ...
    candidate = base
    n = 2
    while True:
        # ensure not in DB *as another user*, and not already chosen this run
        clash = User.search(
            [("login", "=", candidate), ("id", "!=", u.id)], limit=1)
        if not clash and candidate not in new_login_taken:
            break
        candidate = f"{base}.{n}"
        n += 1
    new_login_taken.add(candidate)

    new_email = f"{candidate}@{DOMAIN}"

    try:
        vals = {}
        if u.login != candidate:
            vals["login"] = candidate
        if (u.email or "") != new_email:
            vals["email"] = new_email
        if vals:
            u.write(vals)
            # propagate to partner email so internal mail uses the new addr
            if u.partner_id and u.partner_id.email != new_email:
                u.partner_id.sudo().write({"email": new_email})
        results.append((u.id, u.login, candidate,
                        "OK" if vals else "already correct"))
    except Exception as e:
        results.append((u.id, u.login, candidate, f"ERROR: {e}"))

env.cr.commit()

# ── Audit CSV ─────────────────────────────────────────────────────
csv_path = "/tmp/kob_login_migration.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["uid", "old_login", "new_login", "status"])
    for row in results:
        w.writerow(row)

# ── Summary ───────────────────────────────────────────────────────
ok = sum(1 for r in results if r[3] == "OK")
already = sum(1 for r in results if r[3] == "already correct")
skipped = sum(1 for r in results if r[3].startswith(("PROTECTED", "no ASCII")))
errors = sum(1 for r in results if r[3].startswith("ERROR"))
unchanged = sum(1 for r in results if r[3] == "unchanged")

print(f"\n=== KOB LOGIN MIGRATION COMPLETE ===")
print(f"  Updated:         {ok}")
print(f"  Already correct: {already}")
print(f"  Unchanged:       {unchanged}")
print(f"  Skipped:         {skipped}")
print(f"  Errors:          {errors}")
print(f"  Audit CSV:       {csv_path}")
print()
print("Sample mappings (first 10 updated):")
for r in results:
    if r[3] == "OK":
        print(f"  {r[1]:40s} → {r[2]}")
