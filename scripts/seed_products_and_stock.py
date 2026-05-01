# -*- coding: utf-8 -*-
"""Seed KOB marketplace products + stock 3000 per product per warehouse.

Products: 4 brands × 6 SKUs = 24 products.  Each gets:
  - default_code = SKU
  - x_kob_sku_code = SKU
  - x_kob_brand = brand
  - name = "[SKU] Brand — Product description"
  - type = consu, is_storable = True (Odoo 19 uses 'is_storable' for stockable)
  - sale_ok + purchase_ok
  - list_price (synthetic 100-1000 ฿)

Stock: stock.quant.create_or_update at each company's main stock location,
       qty = 3000 per (product, warehouse).
"""

PRODUCTS = [
    # (brand, sku, description, price)
    ("KISS-MY-BODY",   "KHKB038", "Hair Keratin Booster 38ml",     390),
    ("KISS-MY-BODY",   "KTSD088", "Total Skin Detox 88ml",         590),
    ("KISS-MY-BODY",   "KMI088",  "Moisture Infusion Lotion 88ml", 490),
    ("KISS-MY-BODY",   "KSF180",  "Soft Foam Cleanser 180ml",      350),
    ("KISS-MY-BODY",   "KTMH088", "Tone Masking Hydrator 88ml",    690),
    ("KISS-MY-BODY",   "KTMM088", "Tone Mineral Mist 88ml",        390),

    ("SKINOXY",        "OXY100",  "Oxy Serum 100ml",               890),
    ("SKINOXY",        "OXY050",  "Oxy Cream 50g",                 690),
    ("SKINOXY",        "OXY200",  "Oxy Toner 200ml",               490),
    ("SKINOXY",        "OXYBB30", "BB Cream 30ml",                 590),
    ("SKINOXY",        "OXYSPF",  "Sunscreen SPF50 50ml",          790),
    ("SKINOXY",        "OXYMIST", "Hydra Mist 100ml",              350),

    ("KISS-OF-BEAUTY", "KOB101",  "Vitamin C Brightening Serum",   790),
    ("KISS-OF-BEAUTY", "KOB202",  "Niacinamide Lotion 100ml",      590),
    ("KISS-OF-BEAUTY", "KOB303",  "Retinol Eye Cream 15ml",        890),
    ("KISS-OF-BEAUTY", "KOB404",  "Hyaluronic Acid Mask",          250),
    ("KISS-OF-BEAUTY", "KOB505",  "Salicylic Cleanser 150ml",      450),
    ("KISS-OF-BEAUTY", "KOB606",  "Lip Balm SPF15 5g",             190),

    ("DAENG-GI-MEO-RI","DUT300",  "Black Hair Tonic 300ml",        850),
    ("DAENG-GI-MEO-RI","DUT500",  "Black Shampoo 500ml",          1050),
    ("DAENG-GI-MEO-RI","DUT200",  "Hair Treatment 200g",           650),
    ("DAENG-GI-MEO-RI","DUTOIL",  "Hair Oil 100ml",                550),
    ("DAENG-GI-MEO-RI","DUTMASK", "Hair Mask 250ml",               890),
    ("DAENG-GI-MEO-RI","DUTSPRY", "Volume Spray 200ml",            450),
]

# ── Resolve target warehouses ──────────────────────────────────────────
warehouses = env["stock.warehouse"].search([], order="company_id, id")
if not warehouses:
    raise SystemExit("No warehouses found — run seed_companies_warehouses.py first")

print("Target warehouses:")
for w in warehouses:
    print(f"  [{w.code}] {w.name}  (company: {w.company_id.name})")

# ── Create / update products ───────────────────────────────────────────
created_products = 0
updated_products = 0

# Use first company for the product master (then sharing across companies).
master_company = env["res.company"].browse(1)

ProductT = env["product.template"].with_company(master_company)

for brand, sku, desc, price in PRODUCTS:
    name = f"[{sku}] {desc}"

    existing = ProductT.search([("default_code", "=", sku)], limit=1)
    vals = {
        "name":            name,
        "default_code":    sku,
        "x_kob_sku_code":  sku,
        "x_kob_brand":     brand,
        "list_price":      price,
        "sale_ok":         True,
        "purchase_ok":     True,
    }
    # Odoo 19 stockable flag.  Defaults differ per install — only set if
    # the column exists on product.template / product.product.
    if "is_storable" in ProductT._fields:
        vals["is_storable"] = True
    elif "type" in ProductT._fields:
        vals["type"] = "product"

    if existing:
        existing.write(vals)
        updated_products += 1
    else:
        ProductT.create(vals)
        created_products += 1

env.cr.commit()
print(f"\n=== PRODUCTS ===")
print(f"  Created: {created_products}")
print(f"  Updated: {updated_products}")

# ── Stock adjustment 3000 per product per warehouse ────────────────────
created_quants = 0
updated_quants = 0

for w in warehouses:
    loc = w.lot_stock_id
    for brand, sku, _desc, _price in PRODUCTS:
        product = env["product.product"].search(
            [("default_code", "=", sku)], limit=1,
        )
        if not product:
            continue
        # Direct quant write — bypasses inventory wizard so we don't hit
        # the kob_wms StockQuantPickface override.
        existing = env["stock.quant"].sudo().search([
            ("product_id", "=", product.id),
            ("location_id", "=", loc.id),
        ], limit=1)
        if existing:
            existing.sudo().write({"quantity": 3000.0})
            updated_quants += 1
        else:
            env["stock.quant"].sudo().create({
                "product_id":  product.id,
                "location_id": loc.id,
                "quantity":    3000.0,
            })
            created_quants += 1

env.cr.commit()
print(f"\n=== STOCK ===")
print(f"  Created quants: {created_quants}")
print(f"  Updated quants: {updated_quants}")

# Verify totals
print(f"\n=== TOTAL STOCK BY WAREHOUSE ===")
for w in warehouses:
    qty = env["stock.quant"].search([
        ("location_id", "=", w.lot_stock_id.id),
    ]).mapped("quantity")
    total = sum(qty)
    n = len(qty)
    print(f"  [{w.code}] {w.name}: {n} products, total qty = {total:,.0f}")
