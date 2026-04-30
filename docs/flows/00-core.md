# 00 · core — User / Group / Permission / Company

## Reference

| | Path | URL |
|-|------|-----|
| Odoo 18 user | `odoo-18.0\odoo\addons\base\models\res_users.py` | https://github.com/odoo/odoo/tree/18.0/odoo/addons/base/models/res_users.py |
| Odoo 18 group | `odoo-18.0\odoo\addons\base\models\res_groups.py` | https://github.com/odoo/odoo/tree/18.0/odoo/addons/base/models/res_groups.py |
| Odoo 18 company | `odoo-18.0\odoo\addons\base\models\res_company.py` | https://github.com/odoo/odoo/tree/18.0/odoo/addons/base/models/res_company.py |
| Odoo 18 record rule | `odoo-18.0\odoo\addons\base\models\ir_rule.py` | https://github.com/odoo/odoo/tree/18.0/odoo/addons/base/models/ir_rule.py |
| Odoo 19 user | `odoo-19.0\addons\base\models\res_users.py` | https://github.com/odoo/odoo/tree/master/addons/base/models/res_users.py |

## KOB-ERP files

```
backend/
├── core/
│   ├── models.py           # Company / User / Group / Permission / AuditLog
│   ├── models_audit.py     # ActivityLog (hash-chain)  — see 12-audit.md
│   ├── auth.py             # current_user dep + requires(perm) dep
│   ├── security.py         # argon2 + JWT encode/decode
│   ├── routes.py           # /auth/{login,refresh,me} + /users + /groups + /companies
│   └── schemas.py          # Pydantic input/output for all of the above
└── seed.py                 # Idempotent superuser + admin group + default company
```

## Data shape

```
core.company
  id, code (UNIQUE), name, legal_name, tax_id, address, phone, email,
  currency (3-char), locale (e.g. th-TH), timezone, parent_id, is_active

core.user
  id, email (UNIQUE), password_hash (argon2), full_name,
  is_active, is_superuser, last_login_at,
  default_company_id  → core.company (use_alter=true to break circular FK),
  preferred_locale (default th-TH),
  groups (M2M user_group), companies (M2M user_company),
  default_company (computed via FK)

core.group
  id, name (UNIQUE), description,
  permissions (M2M group_permission), users (M2M user_group)

core.permission
  id, model (e.g. "wms.warehouse"), action ("read"/"write"/"create"/"delete"),
  description; UNIQUE(model, action); code = "model:action"

core.audit_log  (separate from activity_log — see 12-audit.md)
  actor_id, model, record_id, action, before(JSON), after(JSON), request_id
```

## Login & token flow

```
1. POST /api/v1/auth/login { email, password }
   ├── user = SELECT WHERE email=? AND deleted_at IS NULL
   ├── argon2.verify(password, user.password_hash)  →  401 on miss
   ├── if needs_rehash: re-hash with new params  (transparent upgrade)
   ├── user.last_login_at = now()
   └── return { access_token (60min), refresh_token (14d), token_type='bearer' }

2. POST /api/v1/auth/refresh { refresh_token }
   └── decode refresh, ensure type=='refresh', return new pair

3. GET /api/v1/auth/me  (Authorization: Bearer <access>)
   └── decode access, ensure type=='access', SELECT user with selectinload(
        groups, companies, default_company
       )  →  UserRead
```

## RBAC dependency

```python
@router.post("/wms/warehouses",
             dependencies=[Depends(requires("wms.warehouse:write"))])
async def create_wh(...): ...
```

`requires(*perms)` returns a FastAPI dep that:

1. Pulls the current user via `Depends(current_user)`
2. Superuser → pass through
3. Otherwise: `granted = {p.code for g in user.groups for p in g.permissions}`
4. Any missing → 403 with the missing perm code(s)

## Multi-company flow (Phase 9)

```
1. Login returns access_token (no company claim — kept simple)
2. Frontend reads /auth/me → user.companies + user.default_company
3. CompanySwitcher dropdown lists user.companies
4. POST /api/v1/companies/{id}/switch  →  user.default_company_id = id
5. UserRead returned with refreshed companies / default_company
6. Frontend invalidates ALL queries so per-company filtered lists refetch
```

Today our domain models do **not** carry `company_id` yet (they're global per
deployment).  The hooks are in place — the next step is to add
`company_id` FKs and a request-scoped filter on each list endpoint.

## Seed (`uv run python -m backend.seed`)

```
1. _ensure_default_company   → company KOB (currency THB, locale th-TH)
2. _ensure_permissions       → ~50 permissions across all schemas
3. _ensure_admin_group       → group "admin" with every permission
4. _ensure_superuser         → admin@koberp.co.th (env-overridable),
                               attach to admin group + KOB company,
                               default_company_id = KOB.id
5. session.commit()
```

## Frontend

```
frontend/src/
├── lib/auth.tsx                — AuthProvider context (login / logout / refresh)
├── lib/api.ts                  — axios + bearer interceptor + auto-refresh on 401
├── pages/LoginPage.tsx         — single-form login
├── components/CompanySwitcher  — dropdown that calls /companies/{id}/switch
├── components/LanguageSwitcher — i18next changeLanguage
└── pages/UsersPage.tsx         — full Odoo-style List + Kanban + Form on Users
```

## Differences vs Odoo

| | Odoo | KOB-ERP |
|-|------|---------|
| Group inheritance | `implied_ids` chain | flat (no inheritance) |
| Record rules | `ir.rule` per-domain | application-level via `requires()` decorator + per-route filters |
| External ids | XML data | not yet — seed runs imperative Python |
| `res.partner` | shared by users / vendors / customers | each domain owns its own table (vendor, customer, employee.partner) — denormalised on purpose |
| Multi-company | record-rule-based (`company_id` everywhere) | M2M user↔company, default_company drives JWT context, domain FK to be added per phase |
