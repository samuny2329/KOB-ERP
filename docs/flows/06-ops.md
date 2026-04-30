# 06 · ops — Boxes / Platform Orders / KPI / SLA / Worker / Reports

## Reference

| | Path |
|-|------|
| KOB-WMS box | `odoo-18.0\custom_addons\kob_wms\models\wms_box_*.py` |
| KOB-WMS api config | `odoo-18.0\custom_addons\kob_wms\models\wms_api_config.py` |
| Odoo 18 sale_amazon (similar) | `odoo-18.0\odoo\addons\sale_amazon\` (https://github.com/odoo/odoo/tree/18.0/addons/sale_amazon) |
| Odoo 18 hr_attendance | `odoo-18.0\odoo\addons\hr_attendance\` (https://github.com/odoo/odoo/tree/18.0/addons/hr_attendance) |

## KOB-ERP files

```
backend/modules/ops/
├── models.py             — BoxSize, BoxUsage, PlatformConfig, PlatformOrder,
│                           PlatformOrderLine, WorkerKpi, KpiTarget,
│                           KpiAlert, DailyReport, MonthlyReport
├── schemas.py
└── routes.py             — /api/v1/ops/*

backend/modules/wms/models_boxes.py
  BoxSize (computed: volume_cm3, volume_m3, tape_length_m, tape_cost_est)
  ProductBoxRecommendation (best_box_id, usage_frequency, avg_fill_pct)
```

## Data shape (highlights)

```
ops.box_size
  id, code (UNIQUE), name, length_cm, width_cm, height_cm,
  max_weight_kg, cost (Numeric 12,2), active
  volume_cm3            (Python @property: l × w × h)
  dimensional_weight_kg (Python @property: volume_cm3 / 5000)

ops.box_usage
  id, usage_date, warehouse_id, box_size_id, qty_used, qty_wasted

ops.platform_config
  id, platform ∈ {shopee, lazada, tiktok, manual},
  shop_name, shop_id, access_token, refresh_token, token_expires_at,
  webhook_secret, active

ops.platform_order
  id, platform, external_order_id (UNIQUE per config),
  platform_config_id, status ∈ {pending, processing, shipped, completed, cancelled, returned},
  buyer_name, buyer_phone, shipping_address,
  total_amount, currency (default THB), ordered_at,
  warehouse_id, outbound_order_id (FK to outbound.order — set when promoted),
  raw_payload (Text)

ops.platform_order_line
  id, order_id, sku, product_name, qty, unit_price, product_id

ops.worker_kpi  (period snapshot — append-only)
  id, user_id, kpi_date, picks_completed, packs_completed, orders_shipped,
  errors_reported, active_minutes, accuracy_pct, throughput_score
  UNIQUE(user_id, period, period_start)

ops.kpi_target
  id, warehouse_id, metric_name, target_value, warning_pct, critical_pct
  UNIQUE(warehouse_id, metric_name)

ops.kpi_alert  (auto-cleared when resolved)
  id, warehouse_id, user_id, metric_name,
  severity ∈ {info, warning, critical}, message, actual_value, target_value,
  resolved (bool), resolved_at, created_at

ops.sla_config
  id, warehouse_id (UNIQUE), pick_sla_min, pack_sla_min, ship_sla_min,
  escalation_threshold_pct (default 80)

ops.expiry_alert
  id, product_id, lot_id (UNIQUE), expiry_date, alert_days,
  state ∈ {pending, sent, acknowledged}, last_alert_date

ops.daily_report
  id, report_date, warehouse_id, orders_received, orders_shipped, orders_pending,
  picks_completed, transfers_done, quality_checks, quality_fails,
  boxes_used, total_revenue

ops.monthly_report
  id, year, month, warehouse_id, orders_received, orders_shipped,
  avg_processing_hours, return_rate_pct, total_revenue, top_sku
```

## Flows

### A · Provision a Shopee shop

```
1. POST /ops/platform-configs
   { platform: "shopee", shop_name: "KissOfBeauty Shopee TH", shop_id: "12345", active: true }
2. (out-of-band) PATCH the row to attach access_token / refresh_token / webhook_secret
   — kept off the API surface; rotate via DB or admin script
```

### B · Ingest a platform order via webhook (or scheduled poll)

```
3. POST /ops/platform-orders
   { platform: "shopee", external_order_id: "SP-XYZ-001", platform_config_id,
     buyer_name, total_amount: 1250, ordered_at: "2026-04-30T08:00:00+07:00",
     warehouse_id }
   ── unique on (api_config_id, external_order_id), 409 on duplicate
   ── status defaults to "pending"; raw_payload optional

4. (resolver job)  match SKUs → wms.product, customer → sales.customer,
   create outbound.order via service.create_order_with_lines, then
   PATCH /ops/platform-orders/{id}/status?new_status=processing
   and set outbound_order_id on the platform_order row.
```

### C · Box choice and usage tracking

```
5. POST /ops/box-sizes  { code: "BX-S", name: "Small", length_cm: 20, width_cm: 15, height_cm: 10, max_weight_kg: 3, cost: 8.5 }
6. (per shipment, set on packing) POST /ops/box-usage
   { usage_date: today, warehouse_id, box_size_id, qty_used: 1, qty_wasted: 0 }
```

### D · Worker KPI snapshot (called by scheduler)

```
7. POST /ops/kpi/workers
   { user_id, kpi_date, picks_completed: 142, packs_completed: 121, orders_shipped: 95,
     errors_reported: 1, active_minutes: 380, accuracy_pct: 99.2, throughput_score: 87.5 }
8. GET /ops/kpi/alerts?unresolved_only=true   → list of fired thresholds
```

### E · SLA configuration

```
9. POST /ops/sla-configs
   { warehouse_id, pick_sla_min: 30, pack_sla_min: 20, ship_sla_min: 120,
     escalation_threshold_pct: 80 }
```

## Hooks

- Box volume / dimensional-weight / tape consumption are pure-Python
  computed properties — no triggers.  Suite covered by
  `tests/test_phase2d.py::test_box_volume_formula`.
- KPI alerts are written by an analytics job that compares
  `ops.worker_kpi` to `ops.kpi_target` rules.  We don't run that job yet
  in CI — fire-and-forget integration scheduled for Phase 2d follow-up.

## Differences vs Odoo / KOB-WMS

| | KOB-WMS | KOB-ERP |
|-|------|---------|
| Box analytics | computed via SQL view (`wms.box.analytics`) | snapshot stored in `ops.box_usage` + recommendations in `wms.product_box_recommendation` |
| Platform orders | one record per provider with native API call wired in | staging table only — provider clients live in a separate worker (Phase 2d follow-up) |
| KPI engine | computed views + alert rule model | append-only `worker_kpi` snapshot + threshold table; alerts inserted by analytics job |
| Cross-company analytics (`wms.cc.*`) | many bespoke models | not yet — multi-company FKs to be added phase-by-phase |
