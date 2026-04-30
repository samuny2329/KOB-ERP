# KOB-ERP Roadmap

Source of truth for current phase and what comes next. Update as phases
complete. Tag releases as `v0.<phase>-<name>` (e.g. `v0.1-core`).

## Current Status
**Phase 2b — KOB-WMS pick / pack / ship + bento launcher** (complete)
Next: Phase 2c — Cycle counts + quality checks

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

### Phase 2a — WMS foundation ✅
- [x] WMS models: Warehouse, Zone, UomCategory, Uom, ProductCategory, Product, Location, Lot
- [x] Inventory models: StockQuant, TransferType, Transfer (WorkflowMixin), TransferLine
- [x] Pydantic schemas + REST CRUD routes (`/api/v1/wms/*`, `/api/v1/inventory/*`)
- [x] Transfer service: create-with-lines, confirm/done/cancel, quant updates on done
- [x] Permission catalogue extended (12 new perms across wms + inventory)
- [x] 16 passing unit tests (added transfer state-machine spec test)
- [x] Frontend: TanStack Query API client, Layout w/ nav, Products / Warehouses / Transfers pages, StateBadge component

Tag: `v0.2a-wms`

### Phase 2b — KOB-WMS pick / pack / ship ✅
- [x] `wms.rack`, `wms.pickface`, `wms.courier` (master data)
- [x] `outbound.order` + `order_line` w/ 7-state machine
- [x] `outbound.dispatch_batch` + `scan_item` w/ scanning state
- [x] `core.activity_log` w/ SHA-256 hash-chain audit + `verify_chain()`
- [x] 25 passing tests (added 9 outbound + hash-chain tests)
- [x] Frontend: bento app launcher with per-module skeleton variants
- [x] Frontend: Outbound orders + Couriers/Dispatch list pages
- [x] Permission catalogue extended (12 new perms)

Tag: `v0.2b-outbound`

### Phase 2c — Cycle counts + Quality
- [ ] `inventory.count_session`, `count_task`, `count_entry`, `count_adjustment`, `count_snapshot`
- [ ] `quality.check`, `quality.defect`
- [ ] Variance reconciliation flow

Tag: `v0.2c-counts`

### Phase 2d — Operations / KPI / Boxes / Integrations
- [ ] `wms.box.size` + box analytics (fill %, cost)
- [ ] `wms.api.config` + `wms.platform.order` (Shopee/Lazada/TikTok ingest)
- [ ] `wms.worker.performance` + KPI targets + alert rules + SLA config
- [ ] Daily / monthly reports
- [ ] Cross-company analytics (`wms.cc.*`)

Tag: `v0.2d-ops`

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
