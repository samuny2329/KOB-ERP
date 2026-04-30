# Odoo → KOB-ERP Mapping

Source of truth for porting.  Updated phase-by-phase.

## Phase 2a — WMS foundation + Inventory  (current)

These come from Odoo's built-in `stock` / `product` / `uom` modules
(LGPL).  We re-implement the data model in SQLAlchemy from scratch — see
`docs/ARCHITECTURE.md` § "License-safe porting".

| Odoo Model | KOB-ERP Table | Schema | Notes |
|------------|---------------|--------|-------|
| `stock.warehouse` | `wms.warehouse` | wms | code unique per company |
| `stock.location` | `wms.location` | wms | tree via `parent_id`, usage enum |
| `wms.zone` (kob_wms custom) | `wms.zone` | wms | warehouse_id, color_hex |
| `uom.category` | `wms.uom_category` | wms | groups uoms by physical type |
| `uom.uom` | `wms.uom` | wms | factor + uom_type |
| `product.category` | `wms.product_category` | wms | tree via `parent_id` |
| `product.template` | `wms.product_template` | wms | shared metadata |
| `product.product` | `wms.product` | wms | variant; SKU + barcode |
| `stock.lot` | `wms.lot` | wms | per-product lot/serial |
| `stock.quant` | `inventory.stock_quant` | inventory | (location, product, lot) → qty |
| `stock.picking.type` | `inventory.transfer_type` | inventory | inbound/outbound/internal |
| `stock.picking` | `inventory.transfer` | inventory | header, WorkflowMixin |
| `stock.move` | `inventory.transfer_line` | inventory | line w/ qty_demand & qty_done |

## Phase 2b — KOB-WMS pick / pack / ship  (next)

| KOB-WMS Model | KOB-ERP Table | Schema |
|---------------|---------------|--------|
| `wms.rack` | `wms.rack` | wms |
| `wms.pickface` | `wms.pickface` | wms |
| `wms.courier` | `wms.courier` | wms |
| `wms.sales.order` | `outbound.order` | outbound |
| `wms.sales.order.line` | `outbound.order_line` | outbound |
| `wms.courier.batch` | `outbound.dispatch_batch` | outbound |
| `wms.scan.item` | `outbound.scan_item` | outbound |
| `kob.wms.user` | merged into `core.user` | core |
| `wms.activity.log` | `audit.activity_log` (hash-chain) | core |

## Phase 2c — Cycle counts + Quality

| KOB-WMS Model | KOB-ERP Table | Schema |
|---------------|---------------|--------|
| `wms.count.session` | `inventory.count_session` | inventory |
| `wms.count.task` | `inventory.count_task` | inventory |
| `wms.count.entry` | `inventory.count_entry` | inventory |
| `wms.count.adjustment` | `inventory.count_adjustment` | inventory |
| `wms.count.snapshot` | `inventory.count_snapshot` | inventory |
| `wms.quality.check` | `quality.check` | quality (new schema) |
| `wms.quality.defect` | `quality.defect` | quality |

## Phase 2d — Operations / KPI / Boxes / Integrations

`wms.box.size`, `wms.box.analytics`, `wms.api.config`, `wms.platform.order`,
`wms.worker.performance`, `wms.kpi.target`, `wms.kpi.alert.rule`,
`wms.sla.config`, `wms.expiry.alert`, `wms.daily.report`,
`wms.cc.*` cross-company models.  Schema split TBD; some live in
`outbound`, others in a new `analytics` schema.

(Future phases follow the existing Phase 3+ outline in [ROADMAP.md](ROADMAP.md).)
