# -*- coding: utf-8 -*-
"""Seed master data + 400 products from real UAT JSON.

Run inside Odoo shell:

    docker exec -i kob-odoo-19 odoo shell -d kobdb --no-http \
        < scripts/seed_real_uat_products.py

Mirrors the schema observed on kissgroupdatacenter.com:

  * Tags        — FG (Finished Goods) + per-brand tags.
  * Attributes  — Brand, Category, Series.
  * Tracking    — By Lots + use_expiration_date=True.
  * Routes      — Buy / Manufacture (whichever exists).
  * Taxes       — 7% Output VAT / 7% Input VAT (Thai SME default).
  * Companies   — products are GLOBAL (company_id=False) per Odoo
                  conventions; each of the three KOB-group companies
                  (KOB / BTV / CMN) sees the same catalogue.
"""

import json
import logging
from pathlib import Path

_logger = logging.getLogger("kob_seed_products")
_logger.setLevel(logging.INFO)

UAT_JSON = "/mnt/extra-addons/../odoo-scripts/data/uat_data.json"
# Container-side fallback paths
_CANDIDATES = [
    UAT_JSON,
    "/tmp/uat_data.json",
    "/opt/odoo/uat_data.json",
]

raw = None
for p in _CANDIDATES:
    if Path(p).exists():
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"[seed] loaded UAT JSON from {p}")
        break

if not raw:
    raise FileNotFoundError(
        "uat_data.json not found in any of: %s" % _CANDIDATES,
    )

products_in = list(raw.get("products", [])) + list(raw.get("products_no_barcode", []))
print(f"[seed] total products to seed: {len(products_in)}")

# ── 1. Master data: tags ──────────────────────────────────────────
Tag = env["product.tag"] if "product.tag" in env.registry else None
if Tag is not None:
    for tag_name in ("FG", "RM", "PM",
                     "SKINOXY", "KissMyBody", "DaengGiMeoRi",
                     "SmileBox", "RAYRAY"):
        if not Tag.search([("name", "=", tag_name)], limit=1):
            Tag.create({"name": tag_name})

# ── 2. Master data: attributes ────────────────────────────────────
Attr = env["product.attribute"]
AttrVal = env["product.attribute.value"]

def _ensure_attr(name, values):
    a = Attr.search([("name", "=", name)], limit=1)
    if not a:
        a = Attr.create({"name": name, "create_variant": "no_variant"})
    for v in values:
        if not AttrVal.search(
            [("name", "=", v), ("attribute_id", "=", a.id)], limit=1,
        ):
            AttrVal.create({"name": v, "attribute_id": a.id})
    return a

_ensure_attr(
    "Brand",
    ["SKINOXY", "KissMyBody", "DaengGiMeoRi", "SmileBox", "RAYRAY"],
)
_ensure_attr(
    "Category",
    ["Face Care", "Body Care", "Hair Care", "Make-up",
     "Fragrance", "Packaging", "Other"],
)
_ensure_attr(
    "Series",
    ["Bright & Glow", "Dewy & Hydrating", "Anti-Aging",
     "Acne Care", "UV Protect"],
)

# ── 3. Resolve taxes (7% IN/OUT) ─────────────────────────────────
Tax = env["account.tax"]
out_vat = Tax.search([
    ("type_tax_use", "=", "sale"), ("amount", "=", 7),
], limit=1)
in_vat = Tax.search([
    ("type_tax_use", "=", "purchase"), ("amount", "=", 7),
], limit=1)
print(f"[seed] resolved taxes: out={out_vat.name if out_vat else 'NONE'} "
      f"in={in_vat.name if in_vat else 'NONE'}")

# ── 4. Routes (Buy / Manufacture) — IF the modules are installed ─
Route = env["stock.route"]
buy_route = Route.search([("name", "ilike", "buy")], limit=1)
mfg_route = Route.search([("name", "ilike", "manufacture")], limit=1)

# Resolve UoM (Units)
UoM = env["uom.uom"]
unit_uom = UoM.search([("name", "=", "Units")], limit=1) \
           or UoM.search([], limit=1)

# ── 5. Seed products ──────────────────────────────────────────────
ProductT = env["product.template"]
created = 0
updated = 0
skipped = 0

# Pre-cache existing default_codes to avoid repeated searches
existing_codes = {
    p.default_code: p
    for p in env["product.product"].search([
        ("default_code", "!=", False),
    ])
}

# Field gates — Odoo 18+ uses is_storable; older uses type='product'
has_is_storable = "is_storable" in ProductT._fields
has_use_exp = "use_expiration_date" in ProductT._fields
has_tracking = "tracking" in ProductT._fields

route_ids = []
if buy_route:
    route_ids.append(buy_route.id)
if mfg_route:
    route_ids.append(mfg_route.id)

for p in products_in:
    sku = p.get("default_code")
    name = p.get("name") or sku or "Unnamed"
    barcode = p.get("barcode") or False
    p_type = p.get("type") or "consu"

    if not sku:
        skipped += 1
        continue
    if sku in existing_codes:
        # Update key fields only — don't blow away custom edits.
        prod = existing_codes[sku]
        upd = {}
        if barcode and prod.barcode != barcode:
            try:
                prod.barcode = barcode
            except Exception:
                pass
        if has_tracking and prod.tracking != "lot" and p_type != "service":
            prod.tracking = "lot"
        if has_use_exp and not prod.use_expiration_date and p_type != "service":
            prod.use_expiration_date = True
        if route_ids and not prod.route_ids:
            prod.write({"route_ids": [(6, 0, route_ids)]})
        if out_vat and not prod.taxes_id:
            prod.write({"taxes_id": [(4, out_vat.id)]})
        if in_vat and not prod.supplier_taxes_id:
            prod.write({"supplier_taxes_id": [(4, in_vat.id)]})
        updated += 1
        continue

    vals = {
        "name":         name,
        "default_code": sku,
        "barcode":      barcode,
        "type":         p_type if p_type in ("consu", "service") else "consu",
        "uom_id":       unit_uom.id,
        "sale_ok":      True,
        "purchase_ok":  True,
    }
    # uom_po_id was removed in Odoo 19; replaced by purchase_uom_id
    # (optional, defaults to uom_id) — only set if the field exists.
    if "purchase_uom_id" in ProductT._fields:
        vals["purchase_uom_id"] = unit_uom.id
    if has_is_storable and p_type != "service":
        vals["is_storable"] = True
    if has_tracking and p_type != "service":
        vals["tracking"] = "lot"
    if has_use_exp and p_type != "service":
        vals["use_expiration_date"] = True
    if route_ids and p_type != "service":
        vals["route_ids"] = [(6, 0, route_ids)]
    if out_vat:
        vals["taxes_id"] = [(6, 0, [out_vat.id])]
    if in_vat:
        vals["supplier_taxes_id"] = [(6, 0, [in_vat.id])]

    try:
        ProductT.create(vals)
        created += 1
    except Exception as e:
        print(f"[seed] FAIL {sku}: {e}")
        skipped += 1

env.cr.commit()
print(f"[seed] DONE — created={created}, updated={updated}, skipped={skipped}")
print(f"[seed] product.product total now: "
      f"{env['product.product'].search_count([])}")
