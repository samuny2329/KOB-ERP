# KOB-ERP Roadmap

Source of truth for current phase and what comes next. Update as phases
complete. Tag releases as `v0.<phase>-<name>` (e.g. `v0.1-core`).

## Current Status
**Phase 8 — Production Hardening** (complete) ✅
All phases 0–8 shipped. System ready for deployment.

### Phase Legend
- ✅ Complete and tagged
- 🚧 In progress

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

### Phase 2c — Cycle counts + Quality ✅
- [x] `inventory.count_session` (5-state machine) + `count_task` (6-state w/ recount + revert)
- [x] `inventory.count_entry`, `count_adjustment`, `count_snapshot`
- [x] `quality.check` (pending → passed/failed/skipped) + `quality.defect` (3 severities)
- [x] Routes: 8 count endpoints + 5 quality endpoints, all logged into hash-chain
- [x] Frontend: launcher tiles (Counts, Quality, Audit), Counts page, Quality page, Activity log page w/ "Verify chain" button
- [x] 9 new permissions seeded
- [x] 29 tests passing (added 4 Phase 2c state-machine tests)

Tag: `v0.2c-counts`

### Phase 2d — Operations / KPI / Boxes / Integrations ✅
- [x] `ops.box_size` + `box_usage` (fill %, dimensional weight, cost)
- [x] `ops.platform_config` + `ops.platform_order` + `ops.platform_order_line` (Shopee/Lazada/TikTok ingest)
- [x] `ops.worker_kpi` + `ops.kpi_target` + `ops.kpi_alert` (severity: info/warning/critical)
- [x] `ops.daily_report` + `ops.monthly_report` (pre-computed aggregates)
- [x] Frontend: OpsPage with platform orders, KPI alerts, daily reports
- [x] All new modules enabled on bento launcher

Tag: `v0.2d-ops`

### Phase 3 — Purchase + Manufacturing ✅
- [x] `purchase.vendor`, `purchase.purchase_order`, `purchase.po_line`
- [x] `purchase.receipt`, `purchase.receipt_line` with validate action
- [x] `mfg.bom_template`, `mfg.bom_line`
- [x] `mfg.manufacturing_order` (5-state) + `mfg.work_order`
- [x] `mfg.subcon_vendor`, `mfg.subcon_recon`, `mfg.subcon_recon_line`
- [x] Schemas + routes + frontend (PurchasePage, ManufacturingPage)

Tag: `v0.3-purchase-mfg`

### Phase 4 — Sales + CRM (lite) ✅
- [x] `sales.customer`, `sales.sales_order`, `sales.so_line`
- [x] `sales.delivery`, `sales.delivery_line` with validate action
- [x] Schemas + routes + SalesPage (revenue total, customer grid, order table)

Tag: `v0.4-sales`

### Phase 5 — Accounting ✅
- [x] `accounting.account` (chart of accounts, tree, 6 account types)
- [x] `accounting.journal`, `accounting.journal_entry`, `accounting.journal_entry_line`
- [x] Double-entry balance validation on create
- [x] `accounting.tax_rate`
- [x] Schemas + routes + AccountingPage (CoA table, journal entries)

Tag: `v0.5-accounting`

### Phase 6 — HR + Payroll (lite) ✅
- [x] `hr.department` (tree), `hr.employee` (link to user + warehouse)
- [x] `hr.attendance` (clock-in/out, worked_hours computed)
- [x] `hr.leave_type`, `hr.leave` (draft → submitted → approved/rejected)
- [x] `hr.salary_structure`, `hr.salary_rule`, `hr.payslip`, `hr.payslip_line`
- [x] Schemas + routes + HRPage (department chips, employee cards, leave table)

Tag: `v0.6-hr`

### Phase 7 — MCP Server + AI ✅
- [x] `mcp_server/server.py` — FastMCP with 16 tools
- [x] Tools: query_inventory, list_products, list_warehouses, create/list_transfer, confirm/complete_transfer
- [x] Tools: create/list_purchase_orders, create/list_sales_orders
- [x] Tools: list_subcon_recons, list_employees, get_worker_kpis, verify_audit_chain
- [x] Run via `uv run python -m mcp_server.server`

Tag: `v0.7-mcp`

### Phase 8 — Production Hardening ✅
- [x] `Dockerfile.prod` — multi-stage (backend + frontend + nginx)
- [x] `infra/nginx.conf` — rate limiting, gzip, SPA fallback, reverse proxy
- [x] `infra/docker-compose.prod.yml` — Postgres + Redis + backend + nginx
- [x] `migrations/versions/0003_performance_indexes.py` — 24 indexes across all modules
- [x] DB schemas: core, wms, inventory, outbound, quality, ops, purchase, mfg, sales, accounting, hr

Tag: `v1.0`
