"""Seed putaway rules — auto-route incoming receipts to PF zones by SKU prefix.

Logic:
  - K-prefix products → PF-A zone (high velocity, 30-day count)
  - DGM/DUT prefix → PF-B zone
  - SKINOXY/OXY → PF-C
  - MALISSA/AVH/AVS → PF-D
  - All others → PF-E
"""
env = self.env  # noqa: F821

# Find Storage Categories or just use PICKFACE root
pickface = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock/PICKFACE")], limit=1,
)
if not pickface:
    print("PICKFACE not found")
else:
    # 1. Storage categories per zone
    CATEGORIES = ["PF-A High Velocity", "PF-B DGM Brand", "PF-C SKINOXY",
                  "PF-D MALISSA", "PF-E General"]
    cat_map = {}
    for c in CATEGORIES:
        existing = env["stock.storage.category"].search([("name", "=", c)], limit=1)
        if not existing:
            existing = env["stock.storage.category"].create({"name": c})
            print(f"  ✓ Storage Category: {c}")
        cat_map[c] = existing

    # 2. Tag each PF zone with appropriate storage category
    ZONES = {"A": "PF-A High Velocity", "B": "PF-B DGM Brand",
             "C": "PF-C SKINOXY", "D": "PF-D MALISSA", "E": "PF-E General"}
    for letter, cat_name in ZONES.items():
        bins = env["stock.location"].search([
            ("complete_name", "=like", f"K-On/Stock/PICKFACE/PF-{letter}-%"),
        ])
        for b in bins:
            b.storage_category_id = cat_map[cat_name].id
        if bins:
            print(f"  ✓ Zone PF-{letter}: {len(bins)} bins → {cat_name}")
    env.cr.commit()

    # 3. Putaway rules — match SKU prefix to zone
    PUTAWAY = [
        ("K%",       cat_map["PF-A High Velocity"]),     # K-prefix
        ("DGM%",     cat_map["PF-B DGM Brand"]),
        ("DUT%",     cat_map["PF-B DGM Brand"]),
        ("SKINOXY%", cat_map["PF-C SKINOXY"]),
        ("OXY%",     cat_map["PF-C SKINOXY"]),
        ("MALISSA%", cat_map["PF-D MALISSA"]),
        ("AVH%",     cat_map["PF-D MALISSA"]),
        ("AVS%",     cat_map["PF-D MALISSA"]),
    ]
    rules_created = 0
    for sku_pattern, cat in PUTAWAY:
        # Find a sample product matching pattern (Putaway needs concrete product or category)
        prods = env["product.product"].search([
            ("default_code", "=like", sku_pattern),
        ], limit=3)
        if not prods:
            continue
        for p in prods[:1]:  # one rule per pattern is enough demo
            existing = env["stock.putaway.rule"].search([
                ("product_id", "=", p.id),
                ("location_in_id", "=", pickface.id),
            ], limit=1)
            if existing:
                continue
            env["stock.putaway.rule"].create({
                "product_id": p.id,
                "location_in_id": pickface.id,
                "location_out_id": pickface.id,  # Odoo 19: required
                "storage_category_id": cat.id,
                "company_id": 1,
            })
            rules_created += 1
            print(f"  ✓ Putaway: {p.default_code} → {cat.name}")
    env.cr.commit()
    print(f"\n  → {rules_created} putaway rules created")

print("\n=== Final ===")
print(f"  Storage Categories: {env['stock.storage.category'].search_count([])}")
print(f"  Putaway Rules:      {env['stock.putaway.rule'].search_count([])}")
