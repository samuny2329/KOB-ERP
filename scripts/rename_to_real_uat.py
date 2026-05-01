# -*- coding: utf-8 -*-
"""Rename warehouses + companies to match real UAT exactly.

Source of truth:
    C:/Users/kobnb/Desktop/odoo-scripts/data/uat_data.json

Ground truth from that file:
  Companies (3):
    1. บริษัท คิสออฟบิวตี้ จำกัด        — KOB
    2. บริษัท บิวตี้วิลล์ จำกัด           — BTV (Beauty Wills)
    3. บริษัท คอสโมเนชั่น จำกัด        — CMN (Cosmonation = packaging)

  Warehouses (40 in UAT — we keep 4 core for now):
    KOB:
      K-Off  → KOB-WH1 (Offline)
      K-On   → KOB-WH2 (Online)            ← e-commerce default
      K-SPE  → KOB-SHOPEE                  ← Shopee FBS
      K-BOX  → KOB-BOXME
      (plus KCON, KNOT, KC-WS, KC-EB, KC-BT, KC-BO, KC-KV, KC-OR — created lazily)
    BTV:
      B-Off  → BTV-WH1 (Offline)
    CMN:
      CMNW   → CMN-WH                      ← Cosmonation packaging warehouse
      CMNNO  → CMN Not Available
"""

# ── Companies ──────────────────────────────────────────────────────────
RENAMES = {
    1: "บริษัท คิสออฟบิวตี้ จำกัด",
    2: "บริษัท บิวตี้วิลล์ จำกัด",
}

for cid, expected in RENAMES.items():
    c = env["res.company"].browse(cid)
    if c.exists() and c.name != expected:
        c.write({"name": expected})

# Cosmonation might already be id=3 OR id=4 depending on creation order.
# Make sure exactly one company called "บริษัท คอสโมเนชั่น จำกัด" exists.
cmn = env["res.company"].search(
    [("name", "=", "บริษัท คอสโมเนชั่น จำกัด")], limit=1,
)
if not cmn:
    cmn = env["res.company"].create({
        "name": "บริษัท คอสโมเนชั่น จำกัด",
        "currency_id": env.ref("base.THB").id,
    })

co_kob = env["res.company"].browse(1)
co_btv = env["res.company"].browse(2)
co_cmn = cmn

# ── Step 1. Park existing 4 warehouses with sentinel codes to free
#           the target codes (avoid the (code, company_id) unique
#           constraint when renaming pairs that swap codes). ─────────
PARK = [
    # (current_code, sentinel, target_code, target_name, target_company)
    ("KOB1", "ZZA01", "K-Off", "KOB-WH1 (Offline)", co_kob),
    ("KOB2", "ZZA02", "K-On",  "KOB-WH2 (Online)",  co_kob),
    ("BWL1", "ZZB01", "B-Off", "BTV-WH1 (Offline)", co_btv),
    ("CSN1", "ZZC01", "CMNW",  "CMN-WH",            co_cmn),
]

for current_code, sentinel, _nc, _nn, _co in PARK:
    wh = env["stock.warehouse"].search([("code", "=", current_code)], limit=1)
    if wh:
        wh.write({"code": sentinel, "name": sentinel})
        env.cr.commit()

# ── Step 2. Apply target codes ──────────────────────────────────────
for _cc, sentinel, new_code, new_name, target_co in PARK:
    wh = env["stock.warehouse"].search([("code", "=", sentinel)], limit=1)
    if wh:
        wh.write({
            "code":       new_code,
            "name":       new_name,
            "company_id": target_co.id,
        })
        env.cr.commit()

# ── Step 3. Add the e-commerce-relevant extras: K-SPE (Shopee FBS) ──
existing_codes = set(env["stock.warehouse"].search([]).mapped("code"))

EXTRAS = [
    ("K-SPE",  "KOB-SHOPEE",         co_kob),
    ("K-BOX",  "KOB-BOXME",          co_kob),
    ("CMNNO",  "CMN Not Available",  co_cmn),
]

for code, name, co in EXTRAS:
    if code in existing_codes:
        continue
    env["stock.warehouse"].sudo().create({
        "code":       code,
        "name":       name,
        "company_id": co.id,
    })

env.cr.commit()

# ── Report ─────────────────────────────────────────────────────────
print("\n=== COMPANIES ===")
for c in env["res.company"].search([], order="id"):
    print(f"  [{c.id}] {c.name}")

print("\n=== WAREHOUSES ===")
for w in env["stock.warehouse"].search([], order="company_id, code"):
    print(f"  [{w.code:6s}] {w.name:30s} | {w.company_id.name}")

print("\n=== EXISTING PICKINGS REFERENCING THESE WAREHOUSES ===")
for w in env["stock.warehouse"].search([("company_id", "=", co_kob.id)]):
    n = env["stock.picking"].search_count(
        [("location_id.warehouse_id", "=", w.id)],
    )
    print(f"  [{w.code}] {w.name}: {n} pickings")
