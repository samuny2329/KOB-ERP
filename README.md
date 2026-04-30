# KOB-ERP

Standalone ERP for KOB (~100 employees, internal use). Built from scratch on
**FastAPI + React + PostgreSQL**, using Odoo 18 source code and the KOB-WMS
addon as architectural references (not copied — see `docs/ARCHITECTURE.md`
for the license-safe porting methodology).

## Status
**Phase 0 — Foundation.** Auto commit/push hook + project scaffold. No business
logic yet. See `docs/ROADMAP.md` for phase plan.

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis
- **Frontend**: React + TypeScript + Tailwind + TanStack Query
- **Database**: PostgreSQL 16 (multi-schema per module)
- **Auth**: JWT + RBAC
- **Infra**: Docker Compose → AWS EC2

## Layout
```
backend/    # FastAPI app
frontend/   # React app
migrations/ # Alembic
docs/       # Architecture, Odoo mapping, roadmap
scripts/    # Helper scripts (auto-commit, model porter)
```

## Getting Started
Phase 1+ will populate `backend/` and `frontend/`. For now, the only active
piece is the auto-commit hook in `.claude/settings.local.json`.

## License
Internal use only. Methodology: re-implementation from Odoo concepts (no source
code copying — LGPL-safe). See `docs/ARCHITECTURE.md` § "License-safe porting".
