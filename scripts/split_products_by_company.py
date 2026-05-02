# -*- coding: utf-8 -*-
"""Split products → company_id based on brand / SKU pattern.

  Company 1 KOB  — SKINOXY + KissMyBody (and the legacy KOB101… seeds)
  Company 2 BTV  — DaengGiMeoRi
  Company 3 CMN  — Packaging / RM / PM (default_code starts ``031-``)

Anything that doesn't match an explicit rule stays GLOBAL (company_id
= NULL) so the catalogue still has shared items.
"""

import logging
from collections import Counter

_logger = logging.getLogger("kob_split")
_logger.setLevel(logging.INFO)

KOB = 1   # บริษัท คิสออฟบิวตี้ จำกัด
BTV = 2   # บริษัท บิวตี้วิลล์ จำกัด
CMN = 3   # บริษัท คอสโมเนชั่น จำกัด

ProductT = env["product.template"]

def classify(prod):
    """Return company_id (or False to leave global)."""
    code = (prod.default_code or "").upper()
    name = (prod.name or "").upper()
    brand = (prod.x_kob_brand or "").upper() if "x_kob_brand" in prod._fields else ""

    # Packaging / RM / PM — Cosmonation (CMN) factory
    if code.startswith("031-") or code.startswith("030-"):
        return CMN

    # DaengGiMeoRi — Beauty Ville
    if any(s in name for s in ("DAENGGIMEORI", "DAENG GI MEO RI", "DAENG-GI-MEO-RI")) \
       or "DAENGGIMEORI" in brand \
       or code.startswith(("DGS", "DGT", "DJS", "DJT", "DUT")):
        return BTV

    # SKINOXY / KissMyBody / KOB house brands → KOB
    skinoxy_codes = ("SMA", "SMB", "SMD", "STBG", "STDH", "SWB", "OXY")
    kissmybody_codes = ("KW", "KMP", "KLP", "KTLD", "KTAP", "KTCC",
                        "KINN", "KHKB", "KTSD", "KMI", "KSF", "KTMH",
                        "KTMM", "KOB")
    if any(s in name for s in ("SKINOXY", "KISS MY BODY", "KISS-MY-BODY",
                                 "KISSOFBEAUTY", "KISS OF BEAUTY")) \
       or "SKINOXY" in brand or "KISSMYBODY" in brand \
       or any(code.startswith(p) for p in skinoxy_codes + kissmybody_codes):
        return KOB

    return False  # leave global

# ── Apply classification ──────────────────────────────────────────
counts = Counter()
to_update = {KOB: [], BTV: [], CMN: []}

for prod in ProductT.search([]):
    target = classify(prod)
    if not target:
        counts["global"] += 1
        continue
    if prod.company_id and prod.company_id.id == target:
        counts["already_set"] += 1
        continue
    to_update[target].append(prod.id)
    counts[f"to_set_{target}"] += 1

print("[split] classification summary:", dict(counts))

# Apply in batches per company
Company = env["res.company"]
for cid, ids in to_update.items():
    if not ids:
        continue
    company = Company.browse(cid)
    if not company.exists():
        print(f"[split] WARN company id={cid} does not exist — skipping")
        continue
    ProductT.browse(ids).write({"company_id": cid})
    print(f"[split] set company_id={cid} ({company.name}) on "
          f"{len(ids)} templates")

env.cr.commit()

# ── Report final state ────────────────────────────────────────────
print("\n[split] final per-company breakdown:")
total = 0
for cid in (False, KOB, BTV, CMN):
    if cid is False:
        n = ProductT.search_count([("company_id", "=", False)])
        label = "GLOBAL (shared)"
    else:
        n = ProductT.search_count([("company_id", "=", cid)])
        c = Company.browse(cid)
        label = f"company_id={cid} ({c.name})"
    print(f"  {label}: {n}")
    total += n
print(f"  TOTAL templates: {total}")
