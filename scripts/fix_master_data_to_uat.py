# -*- coding: utf-8 -*-
"""Reshape master data to mirror the production/UAT environment.

What the UAT screenshots show:
  Companies (3):
    1. บริษัท คิสออฟบิวตี้ จำกัด     — Kiss of Beauty Co., Ltd.
    2. บริษัท บิวตี้วิลล์ จำกัด        — Beauty Wills Co., Ltd.
    3. บริษัท คอสโมเนชั่น จำกัด     — Cosmonation Co., Ltd.

  Warehouse codes: KOB-WH1, KOB-WH2 (per company) — ไม่ใช่ "KOB"/"OFL"

  Product line format: "[KINN050] KISS-MY-BODY Eau De Parfum Intense 50 ml"
                       i.e. "[SKU] BRAND Description"

  Misc product: "[REV-405102] Logistics Fees" — used by Print_Label-App as
                a marker line to skip (marketplace fee, not a physical SKU).

  Sales team: "eMarketplace"
  Tags: "Online", "OnlineIFS1"
  Pricelist: "Default THB pricelist (THB)"
  Order type: "Normal Order"
  Payment terms: "7 Days" or "Immediate"
"""

# ── 1. Companies ───────────────────────────────────────────────────────
COMPANIES = [
    (1, "บริษัท คิสออฟบิวตี้ จำกัด"),
    (2, "บริษัท บิวตี้วิลล์ จำกัด"),
    (None, "บริษัท คอสโมเนชั่น จำกัด"),  # create if not exists
]

resolved_companies = []
for cid, name in COMPANIES:
    if cid:
        c = env["res.company"].browse(cid)
        c.write({"name": name})
    else:
        c = env["res.company"].search([("name", "=", name)], limit=1)
        if not c:
            c = env["res.company"].create({
                "name": name,
                "currency_id": env.ref("base.THB").id,
            })
    resolved_companies.append(c)

# Make admin a member of all 3
admin = env["res.users"].browse(2)
admin.company_ids = [(6, 0, [c.id for c in resolved_companies])]

# ── 2. Warehouses: KOB-WH1, KOB-WH2 per company ────────────────────────
# Existing 3 warehouses: KOB / OFL / CMN — rename + extend to match UAT
mapping = [
    ("KOB", "KOB1", "KOB-WH1 (Online)",      resolved_companies[0]),
    ("OFL", "KOB2", "KOB-WH2 (Offline)",     resolved_companies[0]),
    ("CMN", "BWL1", "BWL-WH1 (Beauty Wills)", resolved_companies[1]),
]

for old_code, new_code, new_name, company in mapping:
    wh = env["stock.warehouse"].search([("code", "=", old_code)], limit=1)
    if not wh:
        wh = env["stock.warehouse"].search([("code", "=", new_code)], limit=1)
    if wh:
        wh.write({
            "code":       new_code,
            "name":       new_name,
            "company_id": company.id,
        })

# Add a Cosmonation warehouse
cmn_co = resolved_companies[2]
csn_wh = env["stock.warehouse"].search(
    [("company_id", "=", cmn_co.id)], limit=1,
)
if not csn_wh:
    csn_wh = env["stock.warehouse"].sudo().create({
        "name":       "CSN-WH1 (Cosmonation)",
        "code":       "CSN1",
        "company_id": cmn_co.id,
    })

# ── 3. Sales team eMarketplace ─────────────────────────────────────────
team = env["crm.team"].search([("name", "=", "eMarketplace")], limit=1)
if not team:
    team = env["crm.team"].sudo().create({
        "name":       "eMarketplace",
        "company_id": resolved_companies[0].id,
    })

# ── 4. Tags ────────────────────────────────────────────────────────────
for tag_name in ("Online", "OnlineIFS1", "fake_order"):
    if not env["crm.tag"].search([("name", "=", tag_name)], limit=1):
        env["crm.tag"].create({"name": tag_name})

# ── 5. Pricelist + payment terms ──────────────────────────────────────
thb = env.ref("base.THB", raise_if_not_found=False)
if thb:
    pl = env["product.pricelist"].search(
        [("name", "ilike", "Default THB")], limit=1,
    )
    if not pl:
        env["product.pricelist"].create({
            "name":         "Default THB pricelist",
            "currency_id":  thb.id,
            "company_id":   resolved_companies[0].id,
        })

# ── 6. Products: [SKU] BRAND Description format ────────────────────────
# Replaces our seeded scripts/seed_products_and_stock.py output.
PRODUCTS = [
    # (brand,             sku,        description,                          price)
    ("KISS-MY-BODY",      "KINN050",  "Eau De Parfum Intense 50 ml",         372),
    ("KISS-MY-BODY",      "KHKB038",  "Hair Keratin Booster 38 ml",          390),
    ("KISS-MY-BODY",      "KTSD088",  "Total Skin Detox 88 ml",              590),
    ("KISS-MY-BODY",      "KMI088",   "Moisture Infusion Lotion 88 ml",      490),
    ("KISS-MY-BODY",      "KSF180",   "Soft Foam Cleanser 180 ml",           350),
    ("KISS-MY-BODY",      "KTMH088",  "Tone Masking Hydrator 88 ml",         690),
    ("KISS-MY-BODY",      "KTMM088",  "Tone Mineral Mist 88 ml",             390),

    ("SKINOXY",           "OXY100",   "Oxy Serum 100 ml",                    890),
    ("SKINOXY",           "OXY050",   "Oxy Cream 50 g",                      690),
    ("SKINOXY",           "OXY200",   "Oxy Toner 200 ml",                    490),
    ("SKINOXY",           "OXYBB30",  "BB Cream 30 ml",                      590),
    ("SKINOXY",           "OXYSPF",   "Sunscreen SPF50 50 ml",               790),
    ("SKINOXY",           "OXYMIST",  "Hydra Mist 100 ml",                   350),

    ("KISS-OF-BEAUTY",    "KOB101",   "Vitamin C Brightening Serum 30 ml",   790),
    ("KISS-OF-BEAUTY",    "KOB202",   "Niacinamide Lotion 100 ml",           590),
    ("KISS-OF-BEAUTY",    "KOB303",   "Retinol Eye Cream 15 ml",             890),
    ("KISS-OF-BEAUTY",    "KOB404",   "Hyaluronic Acid Mask 25 g",           250),
    ("KISS-OF-BEAUTY",    "KOB505",   "Salicylic Cleanser 150 ml",           450),
    ("KISS-OF-BEAUTY",    "KOB606",   "Lip Balm SPF15 5 g",                  190),

    ("DAENG-GI-MEO-RI",   "DUT300",   "Black Hair Tonic 300 ml",             850),
    ("DAENG-GI-MEO-RI",   "DUT500",   "Black Shampoo 500 ml",               1050),
    ("DAENG-GI-MEO-RI",   "DUT200",   "Hair Treatment 200 g",                650),
    ("DAENG-GI-MEO-RI",   "DUTOIL",   "Hair Oil 100 ml",                     550),
    ("DAENG-GI-MEO-RI",   "DUTMASK",  "Hair Mask 250 ml",                    890),
    ("DAENG-GI-MEO-RI",   "DUTSPRY",  "Volume Spray 200 ml",                 450),
]

ProductT = env["product.template"]
fixed = 0
for brand, sku, desc, price in PRODUCTS:
    name = f"[{sku}] {brand} {desc}"
    p = ProductT.search([("default_code", "=", sku)], limit=1)
    if p:
        p.write({
            "name":         name,
            "x_kob_brand":  brand,
            "list_price":   price,
        })
        fixed += 1

# ── 7. REV-405102 Logistics Fees (service product) ────────────────────
rev = ProductT.search([("default_code", "=", "REV-405102")], limit=1)
rev_vals = {
    "name":          "[REV-405102] Logistics Fees",
    "default_code":  "REV-405102",
    "x_kob_sku_code":"REV-405102",
    "list_price":    27.10,
    "type":          "service",   # service, not stockable
    "sale_ok":       True,
    "purchase_ok":   False,
}
if rev:
    rev.write(rev_vals)
else:
    env["product.template"].create(rev_vals)

env.cr.commit()

# ── Report ─────────────────────────────────────────────────────────────
print("\n=== COMPANIES ===")
for c in env["res.company"].search([], order="id"):
    print(f"  [{c.id}] {c.name}")
    for w in env["stock.warehouse"].search([("company_id", "=", c.id)]):
        print(f"      WH [{w.code}] {w.name}")

print(f"\n=== TEAMS ===")
for t in env["crm.team"].search([]):
    print(f"  {t.name}")

print(f"\n=== TAGS ===")
print(", ".join(env["crm.tag"].search([]).mapped("name")))

print(f"\n=== PRODUCTS (sample) ===")
for p in ProductT.search([], order="default_code")[:6]:
    print(f"  {p.default_code:10s} | {p.name}")
print(f"\n  Total products: {ProductT.search_count([])}")
print(f"  Renamed: {fixed}")
