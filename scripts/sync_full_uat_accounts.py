# -*- coding: utf-8 -*-
"""Sync ALL UAT chart-of-accounts into local kobdb.

  * 1,371 UAT accounts → upsert by (company_id=1, code).
  * Updates ``name``, ``account_type``, ``reconcile``.
  * Creates missing accounts on the fly.

Run via Odoo shell:
    docker exec -i kob-odoo-19 odoo shell -d kobdb --no-http \
        --stop-after-init < scripts/sync_full_uat_accounts.py

Pre-req:
    docker cp scripts/uat_data/kob_uat_accounts_full.json \
        kob-odoo-19:/tmp/kob_uat_accounts_full.json
"""

import json
from pathlib import Path

p = Path("/tmp/kob_uat_accounts_full.json")
if not p.exists():
    raise FileNotFoundError("Run docker cp first")

raw = p.read_bytes()
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]
data = json.loads(raw.decode("utf-8"))
print(f"[acc] loaded {len(data)} UAT accounts (raw, may include per-co dups)")

# Dedup by code — keep the most permissive variant (reconcile=True wins)
seen = {}
for entry in data:
    code = entry.get("c")
    if not code:
        continue
    prev = seen.get(code)
    if prev is None or (entry.get("r") and not prev.get("r")):
        seen[code] = entry
data = list(seen.values())
print(f"[acc] after dedup: {len(data)} unique codes")

# UAT companies 1/2/3 = local 1/2/4 — but accounts are usually
# kept per main company; we sync against company 1 (KOB) which is
# used as the chart template for the group.
LOCAL_CO = 1

Acc = env["account.account"]

# Cache existing local accounts by code (jsonb code_store)
local_by_code = {}
for a in Acc.search([]):
    code = a.code  # auto computed from code_store
    if code:
        local_by_code[code] = a

created = 0
updated = 0
unchanged = 0
errors = 0

for entry in data:
    code = entry.get("c")
    name = (entry.get("n") or "").strip()
    a_type = entry.get("t") or "asset_current"
    reconcile = bool(entry.get("r"))
    if not code or not name:
        continue

    a = local_by_code.get(code)
    if a:
        vals = {}
        if a.name != name:
            vals["name"] = name
        if a.account_type != a_type:
            vals["account_type"] = a_type
        if a.reconcile != reconcile:
            vals["reconcile"] = reconcile
        if vals:
            try:
                a.write(vals)
                updated += 1
            except Exception as e:
                print(f"[acc] FAIL update {code}: {e}")
                errors += 1
        else:
            unchanged += 1
        continue

    # Create
    try:
        Acc.create({
            "code":         code,
            "name":         name,
            "account_type": a_type,
            "reconcile":    reconcile,
            "company_ids":  [(6, 0, [LOCAL_CO])],
        })
        created += 1
    except Exception as e:
        print(f"[acc] FAIL create {code}: {e}")
        errors += 1

env.cr.commit()
print(f"[acc] DONE — created={created} updated={updated} "
      f"unchanged={unchanged} errors={errors}")
print(f"[acc] total accounts now: {Acc.search_count([])}")
print(f"[acc] reconcilable now:   "
      f"{Acc.search_count([('reconcile','=',True)])}")
