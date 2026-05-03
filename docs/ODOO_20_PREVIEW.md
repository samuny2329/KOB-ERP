# Odoo 20 — Release Preview & KOB ERP Migration Notes

**Compiled**: 2026-05-03
**Sources**:
- boyangcs.com/odoo-20-release-date-more-must-know-details
- ksolves.com/blog/odoo/odoo-20-expected-features-release-insights
- vrajatechnologies.com/blog/odoo-20-features-release-date
- apagen.com/odoo-20-is-coming-10-features

> ⚠️ All info below is **community/predicted** — not official Odoo announcement.

---

## Release Window

| Event | Date |
|---|---|
| **Odoo Experience 2026** | Sept 24-26, 2026, Brussels Expo |
| Odoo 20 launch | Same week as Experience |
| General availability | October 2026 |

**Time horizon for KOB ERP**: ~5 months (planning), ~10 months (migration)

---

## Top 10 New Features (most concrete)

1. **Timesheet Timer in Header Bar** — global one-click time tracking
2. **AI Timesheet Assistant** (desktop app) — monitors local activity, proposes entries
3. **Activity Mgmt in Calendar** — reschedule + complete directly from calendar
4. **Field Service merged into Planning** — single scheduling module
5. **Stock Tracking without Inventory app** — light Sales-only stock
6. **Dynamic `Odoo.list()` in Spreadsheets** — live editable ERP lists
7. **Payroll Dashboard with proactive auditing** — flags missing bank/contract before run
8. **Polls in Discuss** — in-chat timed voting
9. **Unified Module Architecture** — many separate modules → core features (less licenses)
10. **Customizable Payslip Layouts** — no-dev formatting

## Major themes

### 🤖 Agentic AI
- Shift from chatbot → **autonomous task executor**
- Predictive analytics: sales forecasting, customer behavior, inventory
- Smart CRM next-best-action
- AI-generated reports + customer communications

### 💰 Finance
- Native predictive **financial forecasting** (budgets vs actuals)
- Improved reconciliation views (scalable)
- Direct government reporting interfaces (regulatory compliance)

### 🏗 Enterprise scalability
- **Read-replica DB support** for 10,000+ user deployments
- Refined offline mode for unstable internet
- More robust architecture for scaling

### 🛒 Sales & subscriptions
- Automated pricing visibility for bundles/complex quotes
- **Native frame agreements** + subscription merging

### 📦 Supply chain
- Proactive replenishment + forecasting-driven actions
- **Advanced packaging** for mixed pallets / complex configs

### 🌐 Website / multilingual
- Independent translations per language (no cross-interference)

---

## Impact on KOB ERP Custom Modules

### High priority (core re-architecture impact)

| Module | Risk | Why |
|---|---|---|
| **kob_extras_v2/v3/v4** | High | Field Service likely merges into Planning → existing FS workflows need re-mapping |
| **kob_wms** + **kob_wms_unified_user** | Medium-High | Inventory app may split — WMS-specific features may move/rename |
| **kob_helpdesk** | Medium | Activity mgmt overhaul changes activity/SLA tracking |
| **kob_kpi_tiles** | Medium | Dashboard widgets may need to leverage new "Dynamic Odoo.list()" pattern |

### Medium priority (likely needs minor adjustment)

| Module | Risk | Why |
|---|---|---|
| kob_account_reports | Medium | New gov reporting interfaces may overlap |
| kob_sales_pro / kob_purchase_pro | Medium | Frame agreements + subscription merging in core |
| kob_thai_compliance | Low-Medium | Direct gov reporting may include Thai locale (or not) |
| kob_logistics_marketing | Low | Stock-without-Inventory may affect light SO flows |

### Low priority (likely safe)

- kob_base, kob_menu_polish, kob_theme, kob_theme_glass — UI overlay, mostly safe
- kob_backup, kob_webhooks, kob_dms_integration — infra/integration, isolated
- kob_my_tasks (🔥 Battle Board) — built on AbstractModel, should be portable
- kob_cycle_count_extra, kob_extras_v2 (cycle count parts) — ForgeFlow OCA upstream may handle

---

## Migration Action Plan

### Phase 1 — Survey (now → Q3 2026)
1. Subscribe to Odoo 20 dev branch (github.com/odoo/odoo) in late Q2 2026
2. Track release notes + breaking changes
3. Inventory all KOB custom modules + mark dependencies on Odoo 19 internals (currently 50+ modules)
4. Pin OCA dependencies (date_range, contract, dms) — wait for OCA Odoo 20 branches

### Phase 2 — Compat staging (Sept-Oct 2026)
1. Spin up Odoo 20 staging instance on dev DB clone
2. Run KOB modules through `odoo --update=all` — collect failures
3. Priority fix order:
   - JS asset import paths (like the `treeFromDomain` fix we did for Odoo 19)
   - View XPath errors (like `o_menu_brand` issue)
   - Model API changes (sql_constraints → models.Constraint already required in Odoo 19)
4. UAT with sample products + transactions

### Phase 3 — Production migration (Q1 2027)
1. Backup full Production DB + filestore
2. Off-hours upgrade window
3. Rollback plan documented
4. Post-migration smoke tests on critical flows (PO → MRP → Inventory → Sale)

---

## Things to Watch Closely

1. **Field Service → Planning merge** — KOB has field-service-like features in extras_v2. If Odoo's planner consolidates this, custom code needs rework.
2. **Stock without Inventory app** — affects how kob_wms's WMS-specific menus relate to standard Inventory app.
3. **Unified module arch** — modules KOB currently uses may merge or change names.
4. **AI features** — could replace some kob_kpi_tiles automation if Odoo's native predictive analytics covers similar scope.
5. **Read-replica DB** — useful for scaling kob_kpi_tiles + heavy reports.

---

## Key Risks for KOB Custom Code

Same patterns we hit during Odoo 18 → 19 migration will recur:
- Frontend JS imports moved between modules (e.g., `treeFromDomain`)
- View XPath targets renamed/removed
- Field renames on standard models (e.g., `detailed_type` removed in Odoo 19)
- Selection labels changed (e.g., `view` usage label `View` → `Virtual`)
- Subcontracting / multi-company constraints tightened
- `_sql_constraints` → `models.Constraint` (already done in Odoo 19, expect more)

---

## Recommended Next Steps

1. **Now**: Don't migrate yet. Stabilize on Odoo 19. Track breaking changes weekly.
2. **June 2026**: Set up Odoo 20 dev clone + run automated tests on KOB modules.
3. **August 2026**: Begin compat patching of high-priority modules.
4. **November 2026**: UAT migration with subset of users.
5. **Q1 2027**: Production migration after Odoo 20.0 hits stability.
