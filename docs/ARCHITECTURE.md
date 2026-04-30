# KOB-ERP Architecture

## Overview
Standalone ERP layered as Frontend → API → Service → ORM → DB.

```
┌─────────────────────────────────────────────┐
│              KOB-ERP Frontend               │
│      React + TypeScript + Tailwind          │
└─────────────────┬───────────────────────────┘
                  │ REST / WebSocket
┌─────────────────▼───────────────────────────┐
│           FastAPI Core Engine               │
│  Auth (JWT)  ORM (SQLAlchemy)  StateMachine │
│  Audit Log   Event Bus         PDF/Report   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              PostgreSQL                     │
│  schemas: core | wms | inventory |          │
│           purchase | mfg | accounting | hr  │
└─────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           Celery + Redis                    │
│   Background: barcode, report, alerts       │
└─────────────────────────────────────────────┘
```

## Schema-per-module
Each module owns a Postgres schema. Cross-module references go through the
`core` schema (users, groups, audit). This keeps migrations independent and
lets us drop/rebuild a module without touching the rest.

## License-safe porting (Odoo → KOB-ERP)

### ✅ Allowed
- Read Odoo model definitions to understand which fields exist, types, and
  relations. Re-implement in SQLAlchemy from scratch.
- Read view XML to understand UX patterns. Re-implement as idiomatic React.
- Read workflow logic to understand state transitions. Re-implement as a
  Python state machine.
- Read tests to understand business rules. Write our own tests, then implement.

### ❌ Forbidden
- Copy-pasting Odoo source code (even Community / LGPL — share-alike applies).
- Verbatim XML view reproduction.
- Copying Odoo SQL.
- Using Odoo Enterprise modules as reference (`account_accountant`,
  `mrp_workorder`, etc.).

### Helper
`scripts/port-odoo-model.py` (Phase 1) reads an Odoo model file and emits a
JSON summary (fields, types, methods, states) — used as a checklist. The
actual code is written from scratch.

## State machine
Generic `WorkflowMixin` provides `state` field and `transition(target)` with
allowed-transitions registry. Each module declares its own states.

Default: `draft → confirmed → done` with `cancelled` as terminal-from-anywhere.

## Audit log
Middleware logs every write op: actor, model, record id, before/after diff,
timestamp. Stored in `core.audit_log`. Read-only API for admin views.

## Auth & RBAC
- JWT access/refresh tokens
- Argon2 password hashing
- Group-based permissions: `(model, action)` tuples e.g. `(wms.transfer, write)`
- Decorator `@requires("wms.transfer:write")` on FastAPI routes
