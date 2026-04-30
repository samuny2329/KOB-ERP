# Odoo → KOB-ERP Mapping

Source of truth for porting. Updated phase-by-phase.

## Phase 2: WMS + Inventory

| Odoo Model | KOB-ERP Table | Schema | Notes |
|------------|---------------|--------|-------|
| `res.users` | `core.user` | core | merge with `kob.wms.user` custom model |
| `res.groups` | `core.group` | core | |
| `res.partner` | `core.partner` | core | unified contact for vendor/customer/employee |
| `stock.warehouse` | `wms.warehouse` | wms | |
| `stock.location` | `wms.location` | wms | hierarchical (parent_id) |
| `stock.quant` | `inventory.stock_quant` | inventory | one row per (location, product, lot) |
| `stock.picking` | `inventory.transfer` | inventory | header |
| `stock.move` | `inventory.transfer_line` | inventory | line |
| `stock.move.line` | `inventory.transfer_line_detail` | inventory | lot/serial detail |
| `product.template` | `wms.product_template` | wms | |
| `product.product` | `wms.product` | wms | variants |
| `stock.lot` | `wms.lot` | wms | |
| `uom.uom` | `wms.uom` | wms | |
| `stock.picking.type` | `inventory.transfer_type` | inventory | inbound/outbound/internal |

## Phase 2b: KOB-WMS custom models

| KOB-WMS Model | KOB-ERP Table | Schema | Notes |
|---------------|---------------|--------|-------|
| `kob.wms.user` | merged into `core.user` | core | extra fields kept (warehouse_id, role) |
| `kob_subcon_recon` | `mfg.recon` | mfg | reconciliation header |
| `kob_subcon_recon_line` | `mfg.recon_line` | mfg | reconciliation lines |

(Expand list per phase. Phases 3–6 mappings will be added when each phase
starts.)
