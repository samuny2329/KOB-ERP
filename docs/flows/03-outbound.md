# 03 · outbound — Pick / Pack / Ship + Dispatch + Couriers

## Reference

| | Path / URL |
|-|------------|
| KOB-WMS sales order | `odoo-18.0\custom_addons\kob_wms\models\wms_sales_order.py` (private) |
| KOB-WMS dispatch | `odoo-18.0\custom_addons\kob_wms\models\wms_courier_batch.py` (private) |
| Odoo 18 stock_picking | `odoo-18.0\odoo\addons\stock\models\stock_picking.py` (https://github.com/odoo/odoo/tree/18.0/addons/stock/models/stock_picking.py) |
| Odoo 18 delivery | `odoo-18.0\odoo\addons\delivery\` (https://github.com/odoo/odoo/tree/18.0/addons/delivery) |

## KOB-ERP files

```
backend/modules/outbound/
├── models.py            — Order, OrderLine, DispatchBatch, ScanItem
├── service.py           — create_order_with_lines, transition_order, scan, dispatch lifecycle
├── schemas.py           — *Create / *Read
└── routes.py            — /api/v1/outbound/* + /api/v1/wms/{racks,pickfaces,couriers}

backend/modules/wms/models_outbound.py
  Rack, Pickface, Courier   (master data lives in wms schema)
```

## Data shape

```
wms.rack          id, zone_id, location_id, code, name, capacity, frozen, active
wms.pickface      id, zone_id, location_id, product_id, code, min_qty, max_qty, active
wms.courier       id, code (UNIQUE), name, sequence, color_hex, tracking_url_template, active

outbound.order   (WorkflowMixin)
  id, ref (UNIQUE), customer_name, platform ∈ {manual,odoo,shopee,lazada,tiktok,pos},
  courier_id, awb, box_barcode, note,
  sla_start_at, pick_start_at, picked_at, pack_start_at, packed_at, shipped_at,
  picker_id, packer_id, shipper_id, state

outbound.order_line
  id, order_id, product_id, lot_id,
  qty_expected, qty_picked, qty_packed, sku, description

outbound.dispatch_batch  (WorkflowMixin)
  id, name (auto "DISP/000123"), courier_id, work_date,
  receiver_name, dispatched_at, dispatched_by, state

outbound.scan_item
  id, batch_id, order_id, barcode, scanned_at, scanned_by
```

## State machine — Order

```
pending  → picking → picked → packing → packed → shipped       (terminal)
       ↓        ↓        ↓        ↓        ↓
       └────────┴────────┴────────┴────────┴──→ cancelled       (terminal)
```

Each transition stamps the corresponding milestone timestamp
(`pick_start_at` / `picked_at` / …).

## State machine — DispatchBatch

```
draft → scanning → dispatched
   ↓        ↓
   └────────┴──→ cancelled
```

## Happy-path flow

```
1. (master data) POST /wms/couriers { code: "FLASH", name: "Flash Express", color_hex: "#fbbf24" }

2. POST /outbound/orders
   { ref: "SO-1042", customer_name: "ลูกค้า A", platform: "manual",
     courier_id: <flash>,
     lines: [ { product_id, qty_expected: 2 }, ... ] }
   ── service.create_order_with_lines:
       ├── insert Order(state="pending", sla_start_at=now())
       ├── insert OrderLines
       └── append_activity("order.created")  — see 12-audit.md

3. POST /outbound/orders/{id}/transition?target=picking      → pick_start_at=now()
4. POST /outbound/orders/{id}/transition?target=picked       → picked_at=now()
5. POST /outbound/orders/{id}/transition?target=packing      → pack_start_at=now()
6. POST /outbound/orders/{id}/transition?target=packed       → packed_at=now()

# Dispatch batch — group multiple packed orders for one courier handover
7. POST /outbound/dispatch-batches { courier_id, work_date }   → name="DISP/000001", state="draft"
8. POST /outbound/dispatch-batches/{batch}/scan { barcode: "AWB-XYZ", order_id: <packed> }
   ── add_scan:
       ├── batch.state must be in {draft, scanning}
       ├── if draft: transition draft → scanning
       ├── insert ScanItem(barcode, order_id, scanned_by, scanned_at)
       └── append_activity("dispatch.scan")
9. POST /outbound/dispatch-batches/{batch}/transition?target=dispatched
   ── batch.dispatched_at = now(); batch.dispatched_by = current_user
   └── append_activity("dispatch.dispatched")

10. (per order) POST /outbound/orders/{id}/transition?target=shipped     → shipped_at=now()
```

## Hooks

- Every order/batch/scan transition appends a row to `core.activity_log`
  (hash-chained — see [12-audit.md](12-audit.md)).
- KPI snapshots in `ops.worker_kpi` are populated by a periodic job that
  reads `picker_id` / `packer_id` / `shipper_id` and the milestone
  timestamps.

## Differences vs Odoo

| | Odoo / KOB-WMS | KOB-ERP |
|-|------|---------|
| Customer ref | `res.partner` linked record | denormalised `customer_name` string for now (Phase 4 will add `sales.customer`) |
| AWB management | `delivery.carrier` + tracking_ref via add-on | flat `awb` field on Order |
| Dispatch signature | `wms.courier.batch.signature` (Binary) | not stored — capture at handheld layer, only `receiver_name` + `dispatched_by` recorded |
| SLA tracking | computed selection (`on_track / at_risk / breached / done`) | computed at read time from milestone timestamps + `ops.sla_config`; not persisted |
