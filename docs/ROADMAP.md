# KOB-ERP Roadmap

Source of truth for current phase and what comes next. Update as phases
complete. Tag releases as `v0.<phase>-<name>` (e.g. `v0.1-core`).

## Current Status
**Phase 1 — Core Engine** (complete, awaiting Postgres-backed integration test)
Next: Phase 2 — WMS + Inventory port

## Phases

### Phase 0 — Foundation ✅
- [x] git init + remote `samuny2329/KOB-ERP`
- [x] Auto commit & push Stop hook
- [x] `.claude/launch.json` (FastAPI 8000, Vite 5173, Odoo 8018 reference)
- [x] Project skeleton (backend/, frontend/, migrations/, docs/, scripts/)
- [x] Initial documentation (ARCHITECTURE, ODOO_MAPPING, ROADMAP)

### Phase 1 — Core Engine ✅
- [x] FastAPI app skeleton ([backend/main.py](../backend/main.py), settings, CORS)
- [x] SQLAlchemy 2.0 async engine + session ([backend/core/db.py](../backend/core/db.py))
- [x] `BaseModel` / `CoreModel` mixins ([backend/core/base_model.py](../backend/core/base_model.py))
- [x] Auth: JWT login/refresh, argon2 ([backend/core/security.py](../backend/core/security.py))
- [x] User / Group / Permission models ([backend/core/models.py](../backend/core/models.py))
- [x] RBAC `@requires` dependency ([backend/core/auth.py](../backend/core/auth.py))
- [x] State machine `WorkflowMixin` ([backend/core/workflow.py](../backend/core/workflow.py))
- [x] Audit log middleware + after_flush hook ([backend/core/audit.py](../backend/core/audit.py))
- [x] Event bus (in-memory pub/sub) ([backend/core/events.py](../backend/core/events.py))
- [x] Alembic config + multi-schema env ([alembic.ini](../alembic.ini), [migrations/env.py](../migrations/env.py))
- [x] pytest harness — 14 passing tests
- [x] Docker Compose (Postgres 16, Redis 7, Adminer) ([docker-compose.yml](../docker-compose.yml))
- [x] Frontend: Vite + React 18 + TS + Tailwind + TanStack Query + Axios
- [x] Login page + auth context with refresh-token interceptor

Tag: `v0.1-core`

### Phase 2 — WMS + Inventory
Port from `kob_wms` addon. See `docs/ODOO_MAPPING.md` for table list.
- [ ] Models (warehouse, location, product, lot, uom, quant, transfer, transfer_line)
- [ ] CRUD APIs
- [ ] React pages (Warehouse list, Location tree, Product list, Transfer form/list)
- [ ] Subcon recon (port from `kob_subcon_recon`)
- [ ] Migration script from Odoo DB → KOB-ERP DB
- [ ] Tests

Tag: `v0.2-wms`

### Phase 3 — Purchase + Manufacturing
- [ ] Vendor, PO, Receipt, 3-way matching
- [ ] BoM, Work Order
- [ ] Subcon flow (Cosmo workflow)

Tag: `v0.3-purchase-mfg`

### Phase 4 — Sales + CRM (lite)
- [ ] Customer, Quotation, Sales Order, Delivery

Tag: `v0.4-sales`

### Phase 5 — Accounting
- [ ] Chart of Accounts
- [ ] Journal Entry (double-entry)
- [ ] AP/AR aging, COGS, Stock Valuation

Tag: `v0.5-accounting`

### Phase 6 — HR + Payroll (lite)
- [ ] Employee, Department, Attendance, Leave
- [ ] Payroll: salary structure → payslip

Tag: `v0.6-hr`

### Phase 7 — MCP Server + AI
- [ ] FastMCP server exposing query/automation tools
- [ ] Claude integration

Tag: `v0.7-mcp`

### Phase 8 — Production Hardening
- [ ] Performance tuning, indexes
- [ ] Docker production image
- [ ] AWS EC2 deploy + Nginx + SSL
- [ ] Monitoring (logs, metrics)
- [ ] Backup/restore

Tag: `v1.0`
