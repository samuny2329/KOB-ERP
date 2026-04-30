# 04 · counts — Cycle counts (Session / Task / Entry / Adjustment / Snapshot)

## Reference

| | Path |
|-|------|
| KOB-WMS count | `odoo-18.0\custom_addons\kob_wms\models\wms_count_*.py` |
| Odoo 18 inventory adjustment | `odoo-18.0\odoo\addons\stock\models\stock_quant.py` (https://github.com/odoo/odoo/tree/18.0/addons/stock/models/stock_quant.py) |
| Odoo 19 inventory | `odoo-19.0\addons\stock\models\stock_inventory.py` (if exists, https://github.com/odoo/odoo/tree/master/addons/stock/models) |

## KOB-ERP files

```
backend/modules/inventory/
├── models_count.py     — CountSession, CountTask, CountEntry, CountAdjustment, CountSnapshot
├── schemas_count.py    — *Create / *Read
└── routes_count.py     — /api/v1/inventory/counts/*
```

## Data shape

```
inventory.count_session     (WorkflowMixin)
  id, name (UNIQUE, e.g. "CC-2026-04"), session_type ∈ {full, cycle},
  warehouse_id, responsible_id, date_start, date_end,
  variance_threshold_pct (default 2.0), note, state

inventory.count_task        (WorkflowMixin)
  id, session_id, location_id, product_id (nullable),
  assigned_user_id, expected_qty, verified_by, verified_at,
  state (note: 6-state w/ recount + revert)
  counted_qty (computed) = sum(entries.qty)
  variance     (computed) = counted_qty − expected_qty

inventory.count_entry
  id, task_id, product_id, lot_id, qty, user_id, scanned_at

inventory.count_adjustment
  id, session_id, task_id, product_id, location_id, qty_variance,
  reason, state ∈ {pending, approved, rejected}, approved_by, approved_at

inventory.count_snapshot   (audit grade — frozen before/after)
  id, session_id, location_id, product_id, qty_before, qty_after, snapshot_at
```

## State machines

### Session

```
draft → in_progress → reconciling → done       (terminal)
   ↓          ↓             ↓
   └──────────┴─────────────┴──→ cancelled    (terminal)
```

### Task (six-state, supports recount + revert)

```
assigned → counting → submitted → verified → approved   (terminal)
                          ↑          ↓
                          └──────────┘     (revert verified → submitted)
                          ↑
              recount: submitted → counting   (auditor sends back for recount)
   any non-terminal → cancelled
```

The *recount* edge (`submitted → counting`) and *revert* edge
(`verified → submitted`) are explicit in `allowed_transitions` — covered
by `tests/test_phase2c.py::test_count_task_state_flow_supports_recount`.

## Happy-path flow

```
1. POST /inventory/counts/sessions
   { name: "CC-2026-04", session_type: "cycle", warehouse_id,
     date_start: "2026-04-01", date_end: "2026-04-30",
     variance_threshold_pct: 2.0 }
   ──>  Session(state="draft")
       └── append_activity("count.session.created")

2. POST /inventory/counts/sessions/{id}/transition?target=in_progress

3. POST /inventory/counts/tasks
   { session_id, location_id, product_id, assigned_user_id, expected_qty: 100 }
   (repeat for every (location, product) pair the session must cover)

4. (handheld) POST /inventory/counts/entries
   { task_id, product_id, qty: 30 }
   ── if task.state == "assigned": auto-flip to "counting"
       (subsequent entries leave it in "counting")

5. POST /inventory/counts/tasks/{id}/transition?target=submitted
   (the worker says "I'm done")

6. POST /inventory/counts/tasks/{id}/transition?target=verified
   ── verified_by = current user; verified_at = now()
   (auditor double-checks)

7a. (happy) POST /inventory/counts/tasks/{id}/transition?target=approved

7b. (recount) POST /inventory/counts/tasks/{id}/transition?target=counting
    (auditor sends task back to the floor — entries can be added/cleared)

8. (when |variance| > threshold)  Adjustment created out-of-band:
   inventory.count_adjustment(state="pending")  →
   POST /inventory/counts/adjustments/{id}/approve
     ── approved_by = current user; approved_at = now()
     └── append_activity("count.adjustment.approved")

9. POST /inventory/counts/sessions/{id}/transition?target=reconciling   (after all tasks approved)
10. POST /inventory/counts/sessions/{id}/transition?target=done
```

## Hooks

- Each transition appends to `core.activity_log` (hash-chain).
- `count_snapshot` rows are inserted by the reconciliation job (not yet
  implemented as a Celery task — manual API call for now).

## Differences vs Odoo

| | Odoo | KOB-ERP |
|-|------|---------|
| Inventory adjustment | one record per quant variance | grouped by `count_session` for audit / KPI tracking |
| State count for tasks | usually 3-state (draft / in progress / done) | 6-state with recount + revert (matches KOB warehouse SOP) |
| Approval queue | `mrp_workorder` style approvals | per-adjustment approval; superuser can bypass |
