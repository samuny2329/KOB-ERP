# -*- coding: utf-8 -*-
"""Seed all 3,357 stock.locations from UAT (kissgroupdatacenter.com).

Source: ``scripts/uat_data/kob_uat_locations.json`` (exported via the
Chrome extension RPC dump).

Strategy:
  * Match warehouse by **code** (K-Off, K-On, B-Off, B-On, CMNW, etc.)
    so id mismatches don't matter.
  * For each location's ``complete_name`` (e.g. ``K-On/Stock/PICKFACE``)
    walk the path under the warehouse's ``view_location_id``,
    creating any missing ancestors as ``usage='view'``.
  * The leaf becomes an internal storage location, with the UAT
    barcode preserved.
  * Skip locations whose warehouse code we don't have locally.

Run via Odoo shell (no HTTP needed):

    docker exec -i kob-odoo-19 odoo shell -d kobdb --no-http \
        --stop-after-init < scripts/seed_uat_locations.py
"""

import json
import logging
from pathlib import Path

_logger = logging.getLogger("kob_seed_locations")

CANDIDATES = [
    "/tmp/kob_uat_locations.json",
    "/mnt/extra-addons/../scripts/uat_data/kob_uat_locations.json",
]
data = None
for p in CANDIDATES:
    if Path(p).exists():
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[loc] loaded {p} — {len(data)} entries")
        break
if data is None:
    raise FileNotFoundError("Run docker cp first")

Loc = env["stock.location"]
WH = env["stock.warehouse"]

# Map UAT warehouse names → local warehouse code → look up record
# (the "code" field is what survives across instances).
NAME_TO_CODE = {
    # KOB (company 1)
    "KOB-WH1 (Offline)":        "K-Off",
    "KOB-WH2 (Online)":         "K-On",
    "KOB-BOXME":                "K-BOX",
    "KOB-SHOPEE":               "K-SPE",
    "Summer Sale 2026":         "K-POS",
    "KOB Consignment":          "KCON",
    "KOB Not Avaliable":        "KNOT",
    # BTV (company 2)
    "BTV-WH1 (Offline)":        "B-Off",
    "BTV-WH2 (Online)":         "B-On",
    "BTV-BOXME":                "B-BOX",
    "BTV-SHOPEE":               "B-SPE",
    "BTV Consignment":          "BCON",
    "BTV Not Available":        "BNOT",
    # CMN (company 3)
    "CMN-WH":                   "CMNW",
    "CMN-WH KK#1":              "CMNW1",
    "CMN Not Available":        "CMNNO",
    # Retail partners — no fixed local code yet
    "Watson":                   "KC-WS",
    "Beautrium":                "KC-BT",
    "Beautycool":               "KC-BC",
    "Better Way":               "KC-BW",
    "Boots":                    "KC-BO",
    "Eve and Boy":              "KC-EB",
    "Konvy":                    "KC-KV",
    "Multy Beauty":             "KC-MB",
    "S.C.Infinite":             "KC-SC",
    "SCommerce":                "KC-SM",
    "Soonthareeya":             "KC-SY",
    "OR Health & Wellness":     "KC-OR",
}

# Build code → warehouse cache once
wh_by_code = {w.code: w for w in WH.search([])}
print(f"[loc] local warehouses by code: {sorted(wh_by_code.keys())}")


def _ensure_path(path_segments, warehouse, company_id):
    """Walk path under warehouse.view_location_id, creating views as
    needed.  ``path_segments`` is the list of segments AFTER the
    warehouse-root prefix (e.g. ['Stock', 'PICKFACE'])."""
    if not warehouse:
        return False
    parent = warehouse.view_location_id
    for seg in path_segments:
        child = Loc.search([
            ("name", "=", seg),
            ("location_id", "=", parent.id),
        ], limit=1)
        if not child:
            return None  # caller handles creation of the leaf
        parent = child
    return parent


created = 0
updated = 0
skipped_no_wh = 0
skipped_view = 0
errors = 0

# Sort by name length so parents are created before their children.
data.sort(key=lambda x: len(x.get("n", "")))

for entry in data:
    name = entry.get("n") or ""
    usage = entry.get("u")
    wh_uat_name = entry.get("w")
    company_id = entry.get("c")
    barcode = entry.get("b")

    if usage == "view":
        # Odoo auto-creates the warehouse-root view; deeper view nodes
        # get created on-demand by _ensure_path.
        skipped_view += 1
        continue

    if not wh_uat_name:
        # Inter-company virtual / customer / supplier — out of scope
        skipped_no_wh += 1
        continue

    code = NAME_TO_CODE.get(wh_uat_name)
    if not code:
        skipped_no_wh += 1
        continue
    wh = wh_by_code.get(code)
    if not wh:
        skipped_no_wh += 1
        continue

    # Strip the leading warehouse-name prefix to get the relative path.
    # complete_name format: "K-On/Stock/K2-A01-05"
    parts = name.split("/")
    if len(parts) < 2:
        # Just the root view — already exists.
        skipped_view += 1
        continue
    # parts[0] is the warehouse prefix; the rest is the path.
    rel_segments = parts[1:]

    # Walk to (and possibly create) the immediate parent.
    parent = wh.view_location_id
    for seg in rel_segments[:-1]:
        child = Loc.search([
            ("name", "=", seg),
            ("location_id", "=", parent.id),
        ], limit=1)
        if not child:
            child = Loc.sudo().create({
                "name":        seg,
                "location_id": parent.id,
                "usage":       "view"
                               if parent == wh.view_location_id
                               else "internal",
                "company_id":  wh.company_id.id,
            })
        parent = child

    leaf_name = rel_segments[-1]
    existing = Loc.search([
        ("name", "=", leaf_name),
        ("location_id", "=", parent.id),
    ], limit=1)
    vals = {
        "name":        leaf_name,
        "location_id": parent.id,
        "usage":       usage if usage != "view" else "internal",
        "company_id":  wh.company_id.id,
    }
    if barcode:
        vals["barcode"] = barcode
    try:
        if existing:
            existing.write({k: v for k, v in vals.items() if k != "name"})
            updated += 1
        else:
            Loc.sudo().create(vals)
            created += 1
    except Exception as e:
        print(f"[loc] FAIL {name}: {e}")
        errors += 1

env.cr.commit()

print(
    f"[loc] DONE — created={created} updated={updated} "
    f"skipped_view={skipped_view} skipped_no_wh={skipped_no_wh} "
    f"errors={errors}",
)
print(f"[loc] total stock.location now: {Loc.search_count([])}")
