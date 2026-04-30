# 05 · quality — Outgoing checks + Defect records

## Reference

| | Path |
|-|------|
| KOB-WMS quality | `odoo-18.0\custom_addons\kob_wms\models\wms_quality_*.py` |
| Odoo 18 quality | `odoo-18.0\odoo\addons\quality\models\` (https://github.com/odoo/odoo/tree/18.0/addons/quality/models) |
| Odoo 19 quality | `odoo-19.0\addons\quality\` (https://github.com/odoo/odoo/tree/master/addons/quality) |

## KOB-ERP files

```
backend/modules/quality/
├── models.py        — Check, Defect (DEFECT_SEVERITIES tuple)
├── schemas.py       — *Create / *Read
└── routes.py        — /api/v1/quality/*
```

## Data shape

```
quality.check         (WorkflowMixin)
  id, order_id (→ outbound.order), order_line_id,
  product_id, lot_id, expected_qty,
  checked_by_id, checked_at, check_notes, state

quality.defect
  id, check_id, product_id, defect_type, severity ∈ {minor, major, critical},
  description, root_cause, action_taken, occurred_at
DEFECT_SEVERITIES = ("minor", "major", "critical")
```

## State machine

```
pending → passed     (terminal)
       ↘ failed      (terminal)
       ↘ skipped     (terminal)
```

All four states are terminal once decided — no rollback.  If a re-inspection
is required, create a *new* `Check` record.

## Happy-path flow

```
1. POST /quality/checks
   { order_id: <packed order>, order_line_id?, product_id, expected_qty: 2,
     check_notes: "Random pull on batch L240501" }
   ──>  Check(state="pending")
       └── append_activity("quality.check.created")

2a. (Pass)
    POST /quality/checks/{id}/transition?target=passed
    ── checked_by_id = current user; checked_at = now()

2b. (Fail with defect)
    POST /quality/checks/{id}/transition?target=failed
    POST /quality/defects
      { check_id, product_id, defect_type: "label_misprint",
        severity: "major", description: "..." }
    ──> Defect (occurred_at=now())
        └── append_activity("quality.defect.recorded")

2c. (Skip — e.g. spot-check skipped due to volume)
    POST /quality/checks/{id}/transition?target=skipped
```

## Gate on outbound flow

Today the `outbound.order` state machine does **not** enforce that all
quality checks are resolved before `packed → shipped`.  The intended
contract is:

> An order with at least one `Check.state == "pending"` (or `"failed"` without
> a follow-up corrective `passed` check) must not be allowed to ship.

Adding that guard is queued for Phase 2c follow-up — track via TODO in
`backend/modules/outbound/service.py::transition_order`.

## Hooks

- Every state transition + every defect insert writes to `core.activity_log`.
- `ops.kpi_alert` rules can fire on `defect_rate_pct` exceeded (configurable).

## Differences vs Odoo

| | Odoo `quality.check` | KOB-ERP `quality.check` |
|-|------|---------|
| State count | pending / pass / fail / no | pending / passed / failed / skipped |
| Quality point template | `quality.point` model defines reusable check templates | none — every check is ad-hoc |
| Test type | spreadsheet / measure / picture / pass-fail | always pass-fail; richer types deferred |
| Failure → defect | optional | strongly encouraged (free-text severity) |
