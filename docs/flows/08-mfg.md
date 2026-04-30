# 08 · mfg — BoM / Manufacturing Order / Work Order / Subcon

## Reference

| | Path |
|-|------|
| Odoo 18 mrp | `odoo-18.0\odoo\addons\mrp\models\` (https://github.com/odoo/odoo/tree/18.0/addons/mrp/models) |
| Odoo 18 mrp_subcontracting | `odoo-18.0\odoo\addons\mrp_subcontracting\models\` (https://github.com/odoo/odoo/tree/18.0/addons/mrp_subcontracting/models) |
| KOB-WMS subcon recon | `odoo-18.0\custom_addons\kob_wms\models\kob_subcon_recon.py` (private) |

## KOB-ERP files

```
backend/modules/mfg/
├── models.py        — BomTemplate, BomLine, ManufacturingOrder, WorkOrder,
│                       SubconVendor, SubconRecon, SubconReconLine
├── schemas.py
└── routes.py        — /api/v1/mfg/*
```

## Data shape

```
mfg.bom_template
  id, code (UNIQUE), product_id (the finished good), version,
  qty (default 1), active

mfg.bom_line
  id, bom_id, component_product_id, qty, uom_id, scrap_pct

mfg.manufacturing_order   (5-state machine)
  id, ref (UNIQUE), bom_id, product_id, qty_planned, qty_done,
  scheduled_date, started_at, ended_at, warehouse_id, state

mfg.work_order
  id, mo_id, name, sequence, planned_minutes, actual_minutes,
  worker_id, started_at, ended_at, state

mfg.subcon_vendor
  id, vendor_id (FK to purchase.vendor), default_lead_days

mfg.subcon_recon       (the "reconciliation" of subcontractor returns)
  id, ref, subcon_vendor_id, period_start, period_end, state, total_diff

mfg.subcon_recon_line
  id, recon_id, product_id, qty_sent, qty_returned, qty_scrap, qty_diff
```

## State machine — ManufacturingOrder

```
draft → confirmed → in_progress → done       (terminal)
   ↓        ↓             ↓
   └────────┴─────────────┴──→ cancelled    (terminal)
```

## Happy-path flow

### A · Define a BoM

```
1. POST /mfg/boms
   { code: "BOM-CRM50", product_id: <Cream 50ml>, qty: 1, lines: [
       { component_product_id: <jar>, qty: 1, uom_id },
       { component_product_id: <emulsion>, qty: 0.05, uom_id, scrap_pct: 1.5 },
       ...
     ] }
```

### B · Run a Manufacturing Order

```
2. POST /mfg/manufacturing-orders
   { bom_id, product_id, qty_planned: 500, scheduled_date, warehouse_id }
   ──>  MO(state="draft")

3. POST /mfg/manufacturing-orders/{id}/transition?target=confirmed
   (reserve components — currently a no-op; full reservation in Phase 2c follow-up)

4. POST /mfg/manufacturing-orders/{id}/transition?target=in_progress
   ── started_at = now()

5. POST /mfg/work-orders
   { mo_id, name: "Step 1: Mix", planned_minutes: 60, sequence: 10 }
   (one or more steps per MO)

6. POST /mfg/work-orders/{id}/start    → state="in_progress", started_at=now()
   POST /mfg/work-orders/{id}/finish   → state="done", ended_at, actual_minutes

7. POST /mfg/manufacturing-orders/{id}/transition?target=done
   ── ended_at = now()
   ── deduct components from stock (BoM lines × qty_done)
   ── increment finished good in stock
   ── qty_done = sum of work-order outputs
```

### C · Subcon recon (Cosmo workflow port)

```
8. POST /mfg/subcon-recons
   { ref: "SR-2026-04", subcon_vendor_id, period_start, period_end,
     lines: [
       { product_id, qty_sent: 1000, qty_returned: 985, qty_scrap: 12 }
     ] }
   ── line.qty_diff = qty_sent − qty_returned − qty_scrap
   ── recon.total_diff = sum(qty_diff)

9. POST /mfg/subcon-recons/{id}/transition?target=submitted    (vendor side)
10. POST /mfg/subcon-recons/{id}/transition?target=approved    (KOB side)
    ── append_activity("subcon.recon.approved")
    ── if total_diff above threshold → KpiAlert (severity scaled by magnitude)
```

## Hooks

- Component reservations are currently non-blocking; the planned guard
  rejects MO confirmation if any component lacks available stock.  Track
  via TODO in `service.confirm_mo` (to be added Phase 3 polish).
- Subcon recon approvals append to `core.activity_log`.  Approving a recon
  with `total_diff > 0` is the trigger for Accounting (Phase 5) to record
  the loss as inventory write-off.

## Differences vs Odoo

| | Odoo `mrp.production` | KOB-ERP `mfg.manufacturing_order` |
|-|------|---------|
| Component consumption | tied to `stock.move` records | direct quant updates on MO done |
| Routing / workcenters | `mrp.routing` + `mrp.workcenter` | not modelled — work orders flat |
| Subcontracting | `mrp.production` w/ `subcontract` flag and partner | dedicated `subcon_recon` model — period-level, not per-MO |
| BoM types | `normal` / `phantom` / `subcontract` | only flat BoM (phantom expansion deferred) |
