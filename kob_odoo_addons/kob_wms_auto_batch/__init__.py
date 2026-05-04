from . import models


# Production defaults sourced from the legacy WMS frontend
# (`Desktop/WMS/src/services/odooApi.js:288-291`):
#   Shopee → Shopee Express
#   Lazada → Lazada Express
#   TikTok → J&T Express
#   anything else (Manual / Odoo / POS) → Kerry Express
PROD_PLATFORM_DEFAULTS = {
    "shopee": "Shopee Express",
    "lazada": "Lazada Express",
    "tiktok": "J&T Express",
    "odoo":   "Kerry Express",
    "manual": "Kerry Express",
    "pos":    "Kerry Express",
}


def post_init_seed_mappings(env):
    """Seed wms.courier.platform.map per-company on first install with the
    production defaults from the legacy WMS frontend. Idempotent — skips
    rows that already exist (per unique(platform, company) constraint)."""
    Courier = env["wms.courier"].sudo()
    Map = env["wms.courier.platform.map"].sudo()

    # Make sure the named couriers exist (codes match old WMS AWB prefixes)
    courier_seeds = [
        ("Shopee Express", "SPXTH"),
        ("Lazada Express", "LZTH"),
        ("J&T Express",    "JTTH"),
        ("Kerry Express",  "KETH"),
        ("Flash Express",  "FLTH"),
        ("Thai Post",      "TPTH"),
    ]
    for name, code in courier_seeds:
        if not Courier.search([("name", "=", name)], limit=1):
            Courier.create({"name": name, "code": code, "sequence": 10})

    for company in env["res.company"].sudo().search([]):
        for platform, courier_name in PROD_PLATFORM_DEFAULTS.items():
            if Map.search_count([
                ("platform", "=", platform),
                ("company_id", "=", company.id),
            ]):
                continue
            courier = Courier.search([("name", "=", courier_name)], limit=1)
            if not courier:
                continue
            Map.create({
                "platform": platform,
                "courier_id": courier.id,
                "company_id": company.id,
                "note": "Production default (legacy WMS)",
            })
