# 01 · wms — Warehouse / Zone / Location / Product / Lot / UoM

## Reference

| | Path | URL |
|-|------|-----|
| Odoo 18 stock | `odoo-18.0\odoo\addons\stock\models\` | https://github.com/odoo/odoo/tree/18.0/addons/stock/models |
| Odoo 18 product | `odoo-18.0\odoo\addons\product\models\` | https://github.com/odoo/odoo/tree/18.0/addons/product/models |
| Odoo 18 uom | `odoo-18.0\odoo\addons\uom\models\` | https://github.com/odoo/odoo/tree/18.0/addons/uom/models |
| KOB-WMS zone | `odoo-18.0\custom_addons\kob_wms\models\wms_zone.py` | (private) |
| Odoo 19 stock | `odoo-19.0\addons\stock\models\` | https://github.com/odoo/odoo/tree/master/addons/stock/models |

## KOB-ERP files

```
backend/modules/wms/
├── models.py             — Warehouse, Zone, Location, UomCategory, Uom, ProductCategory, Product, Lot
├── models_outbound.py    — Rack, Pickface, Courier (used by outbound module)
├── models_boxes.py       — BoxSize, ProductBoxRecommendation (used by ops module)
├── schemas.py            — *Create / *Read for the above
└── routes.py             — CRUD under /api/v1/wms/*
```

## Data shape

```
wms.uom_category   id, name (UNIQUE)
wms.uom            id, category_id, name, uom_type ∈ {reference,bigger,smaller},
                   factor (Numeric 16,6 vs reference), rounding, active
                   UNIQUE(category_id, name)

wms.warehouse      id, code (UNIQUE), name, address, active
wms.zone           id, warehouse_id, code, name, color_hex, note, active
                   UNIQUE(warehouse_id, code)

wms.location       id, warehouse_id, parent_id (tree), zone_id,
                   name, complete_name, usage ∈ LOCATION_USAGES, barcode, active
                   UNIQUE(warehouse_id, barcode)
wms.LOCATION_USAGES = (supplier, customer, internal, inventory, transit, view, production)

wms.product_category   id, parent_id (tree), name, complete_name
wms.product            id, default_code (SKU, UNIQUE), barcode (UNIQUE),
                       name, description, type ∈ {consu,service,product},
                       category_id, uom_id, list_price (Numeric 14,2),
                       standard_price, active

wms.lot                id, product_id, name, expiration_date, note
                       UNIQUE(product_id, name)
```

## Happy-path flows

### A · Create a warehouse and a tree of locations

```
1. POST /wms/warehouses { code: "WH1", name: "Main DC" }
2. POST /wms/locations  { warehouse_id, name: "Stock", usage: "internal" }   (root)
3. POST /wms/locations  { warehouse_id, parent_id: <root>, name: "Aisle-A" }
4. POST /wms/locations  { warehouse_id, parent_id: <Aisle-A>, name: "Shelf-A1", barcode: "WH1-A1" }
```

### B · Catalogue a product

```
1. POST /wms/uom-categories  { name: "Unit" }                  (one-time)
2. POST /wms/uoms            { category_id, name: "PCS", uom_type: "reference", factor: 1 }
3. POST /wms/product-categories  { name: "Skincare" }
4. POST /wms/products            { default_code: "SK-001", name: "Cream 50ml",
                                   type: "product", category_id, uom_id,
                                   list_price: 590, standard_price: 220 }
5. POST /wms/lots                { product_id, name: "L240501", expiration_date: "2027-05-01" }
```

## Hooks / side-effects

- Every write enters `core.audit_log` via the `after_flush` SQLAlchemy hook
  (see [12-audit.md](12-audit.md)).
- No state machine on these masters — they're flagged active/inactive only.
- Cascading deletes:
  - `warehouse.locations`  → CASCADE
  - `warehouse.zones`      → CASCADE
  - `uom_category.uoms`    → CASCADE
  - `product.lots`         → CASCADE

## Differences vs Odoo

| | Odoo | KOB-ERP |
|-|------|---------|
| Product template / variant | split into `product.template` + `product.product` | collapsed into `wms.product` (variants deferred until business needs them) |
| Location parent path | materialised `parent_path` text column | not materialised — recursive CTEs at query time |
| Routes / push / pull rules | `stock.route` + `stock.rule` | not implemented (transfers always between explicit src/dst) |
| Costing methods | per-product (`standard`, `fifo`, `average`) | only `standard_price` stored; FIFO/avg deferred to Phase 5 (accounting) |
