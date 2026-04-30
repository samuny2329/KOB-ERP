# KOB-ERP Roadmap

Source of truth for current phase and what comes next. Update as phases
complete. Tag releases as `v0.<phase>-<name>` (e.g. `v0.1-core`).

## Current Status
**Phase 0 — Foundation** (in progress)

## Phases

### Phase 0 — Foundation ✅
- [x] git init + remote `samuny2329/KOB-ERP`
- [x] Auto commit & push Stop hook
- [x] `.claude/launch.json` (FastAPI 8000, Vite 5173, Odoo 8018 reference)
- [x] Project skeleton (backend/, frontend/, migrations/, docs/, scripts/)
- [x] Initial documentation (ARCHITECTURE, ODOO_MAPPING, ROADMAP)

### Phase 1 — Core Engine
- [ ] FastAPI app skeleton (`backend/main.py`, settings, CORS)
- [ ] SQLAlchemy 2.0 base + session management
- [ ] `BaseModel` (id, timestamps, soft delete, audit fields)
- [ ] Auth: JWT login/refresh, argon2 password hashing
- [ ] RBAC: User, Group, Permission + `@requires` decorator
- [ ] State machine: `WorkflowMixin` (draft → confirmed → done → cancelled)
- [ ] Audit log middleware
- [ ] Event bus (in-memory pub/sub)
- [ ] Alembic init + first migration
- [ ] pytest harness + fixtures
- [ ] Docker Compose (Postgres 16, Redis 7, Adminer)
- [ ] Frontend init (Vite + React + TS + Tailwind + TanStack Query + shadcn/ui)
- [ ] Login page + auth flow

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
