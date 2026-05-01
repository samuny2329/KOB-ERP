# KOB ERP — Odoo 19 addons

This directory turns a stock Odoo 19 install into the **KOB ERP** distribution.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  KOB ERP (the product)                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  kob_odoo_addons/   ← this folder                    │   │
│  │    kob_base                  (branding + menus)      │   │
│  │    kob_theme                 (SAP Fiori web theme)   │   │
│  │    kob_thai_compliance       (Phase 14 port — done)  │   │
│  │    kob_group              (Phase 11/12 — TODO)       │   │
│  │    kob_marketplace        (Phase 10 multi-platform)  │   │
│  │    kob_purchase_extras    (Phase 7 — vendor scoring) │   │
│  │    kob_sales_extras       (Phase 10 — LTV, channel)  │   │
│  │    kob_mfg_extras         (Phase 8 — OEE, shifts)    │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼ depends on                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Odoo 19 stock                                       │   │
│  │  C:\Users\kobnb\Desktop\odoo-19.0  (read-only)       │   │
│  │    base, web, sale, purchase, stock, mrp,            │   │
│  │    hr, account, ...                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

We **do not** modify Odoo's source — every customisation goes in our
addons here, either as new models or `_inherit` extensions.

## Phase mapping (standalone KOB ERP → Odoo addons)

| Standalone phase | Odoo standard | KOB addon |
|-----------------|---------------|-----------|
| Phase 1-2 (WMS basics) | `stock` | covered by stock |
| Phase 3 (Inventory adv) | `stock`, `stock_account` | covered |
| Phase 4 (Outbound) | `stock.picking` | covered |
| Phase 5 (Counts) | `stock`'s physical inventory | covered |
| Phase 6 (Quality) | `quality` | covered (Enterprise) |
| Phase 7 (Purchase adv) | `purchase` | `kob_purchase_extras` |
| Phase 8 (Mfg adv) | `mrp` | `kob_mfg_extras` |
| Phase 10 (Sales adv) | `sale` | `kob_sales_extras` |
| Phase 11/12 (Group) | multi-company | `kob_group` |
| **Phase 14 (Thai compl)** | `hr`, `account` | **`kob_thai_compliance`** |

## Running

```bash
# from C:\Users\kobnb\Desktop\KOB ERP
docker compose -f docker-compose.odoo.yml up -d
# wait ~60s for first install
open http://localhost:8069
# master password: kob-master
# create db → install kob_base + kob_theme + kob_thai_compliance
```

The standalone FastAPI/React stack is **kept** at `backend/` and `frontend/`
as a parallel API — not retired, but no longer the primary KOB ERP UI.
