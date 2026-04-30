# 12 · audit — Activity log (SHA-256 hash chain)

## Reference

| | Path |
|-|------|
| KOB-WMS activity log | `odoo-18.0\custom_addons\kob_wms\models\wms_activity_log.py` (private) |
| Odoo 18 mail.activity | `odoo-18.0\odoo\addons\mail\models\mail_activity.py` (https://github.com/odoo/odoo/tree/18.0/addons/mail/models/mail_activity.py) — different concept (CRM activities), included for context only |
| Odoo 18 audittrail (Enterprise) | concept-only reference; not copied |

## KOB-ERP files

```
backend/core/
├── models_audit.py     — ActivityLog model + compute_block_hash + verify_chain
├── audit.py            — `core.audit_log` SQLAlchemy after_flush hook (column-level diffs)
└── routes.py           — /api/v1/audit/activity-log + /verify  (in core_router)

frontend/src/pages/ActivityLogPage.tsx — table + "Verify chain" button
```

## Two distinct audit streams

KOB-ERP runs **two** audit streams side by side:

1. `core.audit_log` (per-row column-level diffs)
   - **What**: every SQLAlchemy write — create / update / delete with before/after JSON.
   - **How**: `after_flush` event listener in `backend/core/audit.py`.
   - **Why**: forensic "what changed when" log, queried by support.

2. `core.activity_log` (operational milestones with hash-chain)
   - **What**: business events — orders moved through states, dispatches scanned,
     adjustments approved, etc.
   - **How**: explicit `await append_activity(...)` calls inside service code.
   - **Why**: tamper-evident operational audit trail (e.g. for ISO/finance audit).

This document focuses on stream **#2** — the hash chain.

## Data shape

```
core.activity_log
  id, actor_id, action, ref, code, note, occurred_at,
  prev_hash (64-char hex, NULL for first row),
  block_hash (64-char hex)
  Indexes on actor_id, action, ref, block_hash
```

## Hash construction

```python
def compute_block_hash(*, actor_id, action, ref, code, note, occurred_at, prev_hash) -> str:
    payload = {
        "actor_id":    actor_id,
        "action":      action,
        "ref":         ref,
        "code":        code,
        "note":        note,
        "occurred_at": occurred_at.isoformat(),
        "prev_hash":   prev_hash,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

The use of `sort_keys=True` + `separators=(",", ":")` produces a *stable*
canonical string — re-derivable in any language with the same algorithm.

## Append flow

```
async def append_activity(session, *, actor_id, action, ref=None, code=None, note=None):
    last      = SELECT * FROM activity_log ORDER BY id DESC LIMIT 1
    prev_hash = last.block_hash if last else None
    occurred  = datetime.now(UTC)
    block     = compute_block_hash(actor_id=..., ..., occurred_at=occurred, prev_hash=prev_hash)
    INSERT (... prev_hash, block_hash) VALUES (...)
```

This runs inside the same transaction as the business write — so an
order's state transition + its activity row commit atomically.

## Verify-chain flow

```
GET /api/v1/audit/activity-log/verify  →  { valid, broken_at_id }

async def verify_chain(session) -> tuple[bool, int | None]:
    rows = SELECT * FROM activity_log ORDER BY id ASC
    prev = None
    for row in rows:
        expected = compute_block_hash(
            actor_id=row.actor_id, action=row.action, ref=row.ref,
            code=row.code, note=row.note, occurred_at=row.occurred_at,
            prev_hash=prev,
        )
        if expected != row.block_hash or row.prev_hash != prev:
            return False, row.id      # first broken row id
        prev = row.block_hash
    return True, None
```

If anyone tampers with **any field** on **any row**, the recomputed
`block_hash` will not match the stored one — and every subsequent row's
`prev_hash` will be wrong as well, so `broken_at_id` will be the *first*
affected row (audit-friendly).

Tampering scenarios covered by `tests/test_outbound_workflow.py`:

- changing `actor_id` on a row → mismatch
- changing `action` → mismatch
- changing `ref` → mismatch
- changing `note` → mismatch
- inserting/deleting a row in the middle → all subsequent prev_hashes mismatch

## Frontend

`ActivityLogPage.tsx`:

- Paginated table (100 rows by default), columns: time, actor, action,
  ref, note, hash prefix.
- "Verify chain" button at top right calls `/audit/activity-log/verify`
  and shows a green "Chain is intact" or red "Chain broken at row #N"
  banner.

## What gets logged

| Module | Action codes |
|--------|--------------|
| outbound | `order.created`, `order.{picking,picked,packing,packed,shipped,cancelled}`, `dispatch.created`, `dispatch.scan`, `dispatch.{scanning,dispatched,cancelled}` |
| counts | `count.session.created`, `count.session.{in_progress,reconciling,done,cancelled}`, `count.task.{counting,submitted,verified,approved,cancelled}`, `count.adjustment.approved` |
| quality | `quality.check.created`, `quality.check.{passed,failed,skipped}`, `quality.defect.recorded` |
| accounting | `accounting.entry.posted`, `accounting.entry.cancelled` |
| hr | `hr.leave.{submitted,approved,rejected}`, `hr.payslip.paid` |
| mfg | `subcon.recon.{submitted,approved,rejected}` |

The set is deliberately curated — not every CRUD shows up here, only the
events a finance / ops auditor needs to reconstruct the operational
narrative.

## Differences vs Odoo / classic audit modules

| | Classic audit modules (e.g. Odoo Enterprise auditlog) | KOB-ERP `core.activity_log` |
|-|------|---------|
| Trigger | DB-level after_write on every model | explicit `append_activity()` calls in service code |
| Tamper resistance | none / app-level only | SHA-256 hash chain — any tamper detected by `verify_chain` |
| Granularity | every column on every model | curated business events only |
| Storage | unbounded write volume | bounded — events selected per module |
| Performance | trigger overhead on every write | only on selected milestones |

The complementary `core.audit_log` (stream #1) catches the rest by
listening to SQLAlchemy `after_flush` — see `backend/core/audit.py`.
