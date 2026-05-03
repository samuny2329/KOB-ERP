# Odoo 20 → KOB ERP (Odoo 19) Backport Plan

**Goal**: Build Odoo 20 features now into KOB ERP (Odoo 19) — get value 5–10 months early. When Odoo 20 GA (Oct 2026), our custom modules align/replace cleanly with Odoo native versions.

**Date**: 2026-05-03

---

## ✅ Quick wins (1–3 days each, pure JS/OWL or small models)

### 1. Timesheet Timer in header bar
**Spec**: Click once anywhere → start/stop time tracking. Display elapsed time in navbar.
**Implementation**:
- New module `kob_timesheet_navbar`
- Add OWL Component to `web.assets_backend` patching the navbar
- Persistent state in `localStorage` + `account.analytic.line` create on stop
- Use existing `hr.timesheet` if installed, else lightweight `kob.timer.entry` model
**Effort**: ~2 days
**Risk**: Low — purely additive

### 2. Polls in Discuss
**Spec**: `/poll Question? Option1, Option2, Option3` slash command in Discuss → creates voting message with timed expiry.
**Implementation**:
- New module `kob_discuss_polls`
- Model `kob.poll` (question, options m2o, expires_at, creator_id)
- Model `kob.poll.vote` (poll_id, user_id, option_id) with unique constraint
- OWL Component for inline poll display in mail.message thread
- Slash command registration in `composer` registry
**Effort**: ~3 days
**Risk**: Low

### 3. Activity Management in Calendar View
**Spec**: Reschedule + complete activities directly from calendar with one click.
**Implementation**:
- Inherit `mail.activity.calendar` view
- Add inline drag-to-reschedule and "Mark done" overlay button
- Use existing `mail.activity.action_done()` API
**Effort**: ~1 day
**Risk**: Low

---

## 🟡 Medium-effort (1–2 weeks each)

### 4. Stock Tracking without Inventory app
**Spec**: View product stock + record deliveries from Sales module without full Inventory install.
**Implementation**:
- Inherit `sale.order` to add Smart Button "Stock" → simple list of stock.quant
- Add "Quick Deliver" wizard creating stock.picking on the fly
- Make works even when only `stock` module is installed (not warehouse/inventory full)
**Effort**: ~5 days
**Risk**: Medium — touches stock data flow

### 5. Payroll Dashboard with proactive auditing
**Spec**: Dashboard before payroll run flags missing bank, expired contracts, missing payslip data.
**Implementation**:
- New module `kob_payroll_dashboard` (depends `hr_payroll`)
- TransientModel `kob.payroll.dashboard` with computed audit fields
- OWL client action with traffic-light tiles (red/amber/green per category)
- One-click drill into problematic employees
**Effort**: ~7 days
**Risk**: Medium

### 6. Dynamic ERP-list in Spreadsheets
**Spec**: `=ODOO.LIST("model", "domain", ["fields"])` in spreadsheets returns live editable list.
**Implementation**:
- Use OCA `documents_spreadsheet` as base
- Add formula handler `ODOO.LIST` that queries via `/web/dataset/call_kw`
- Two-way sync: edits in spreadsheet → ORM write
**Effort**: ~10 days
**Risk**: Medium-High — spreadsheet engine intricacies

### 7. Customizable Payslip Layout
**Spec**: HR edits payslip PDF format directly from dashboard.
**Implementation**:
- WYSIWYG layout editor (react-grid-layout) for QWeb report blocks
- Save layout as `ir.ui.view` arch
- Preview before commit
**Effort**: ~10 days
**Risk**: Medium

---

## 🔴 High-effort but very valuable (2–4 weeks each)

### 8. Agentic AI for autonomous task execution
**Spec**: AI agent that proactively executes workflows — e.g., chase late POs, suggest reorder, draft customer reply.
**Implementation**:
- Use Anthropic Claude or OpenAI via `requests` from server actions
- Model `kob.ai.agent.run` (prompt, model, output, status)
- Cron action for periodic checks (overdue invoices, stock-out, etc.)
- Tool-use pattern: agent emits intent → human approves → execute
- Integrate with existing kob_my_tasks Battle Board for action queue
**Effort**: ~15 days
**Risk**: High — LLM cost, hallucination guardrails, security
**Pre-req**: Anthropic API key + budget caps

### 9. Predictive Financial Forecasting
**Spec**: Forecast next-quarter revenue/expense from budgets + actuals + sales velocity.
**Implementation**:
- Module `kob_finance_forecast` (depends `kob_account_reports`, `account_budget`)
- Model `kob.finance.forecast` with monthly/quarterly buckets
- Compute: `actual_ytd + (avg_velocity × remaining_periods)`
- Add seasonality adjustment via 3-year moving average
- OWL dashboard with Plotly charts
**Effort**: ~12 days
**Risk**: Medium-High — accuracy expectations, accounting precision

### 10. Read-replica DB support
**Spec**: Route read queries (reports, dashboards) to PostgreSQL replica → primary handles writes only.
**Implementation**:
- PostgreSQL streaming replication setup (infra)
- Patch Odoo's `Cursor` to detect read-only requests → route to replica
- Use `db_replica_uri` config option
- Must whitelist read-only registry methods
**Effort**: ~7 days infra + 7 days code testing
**Risk**: High — query routing edge cases, replication lag

### 11. Offline mode (PWA refinements)
**Spec**: Inventory/sales workflows work offline → sync when reconnected.
**Implementation**:
- Service Worker caching key views
- IndexedDB queue for create/write operations
- Conflict resolution UI on reconnect
- Affect scope: only WMS handheld workflows (kob_wms)
**Effort**: ~15 days
**Risk**: High — sync conflicts, data integrity

---

## 📦 Infrastructure / minor improvements

### 12. Advanced packaging for mixed pallets
**Spec**: One pallet contains multiple SKUs with different qty per layer.
**Implementation**:
- Extend `stock.package_type` with mixed_layers flag
- BOM-like structure for pallets
- Override picking validation to allow mixed
**Effort**: ~5 days

### 13. Frame agreements + subscription merging
**Spec**: Multi-period framework agreements in PO, merge same-vendor subscriptions.
**Implementation**:
- Extend `kob_purchase_pro` with `kob.purchase.frame.agreement`
- Add merge action on `sale.subscription` (if installed)
**Effort**: ~7 days

---

## 🎯 Recommended Priority (next 6 months)

| Phase | What | Why now |
|---|---|---|
| **Phase 1 (Q3 2026)** | #1 Timesheet Timer, #2 Polls, #3 Activity Calendar | Quick wins → user-visible improvements |
| **Phase 2 (Q3-Q4 2026)** | #5 Payroll Dashboard, #4 Stock w/o Inventory | Solve real KOB pain |
| **Phase 3 (Q4 2026)** | #9 Financial Forecasting, #8 Agentic AI (POC) | High ROI when built right |
| **Phase 4 (Q1 2027)** | #10 Read-replica, #11 Offline mode | Scaling foundation before full Odoo 20 migration |

## 🚫 Don't build now (wait for Odoo 20 native)

- **Field Service merge into Planning** (#4 in preview) — wait for Odoo 20's native consolidation
- **Customizable Payslip Layout** (#10 in preview) — Odoo 20 may ship this; building twice = waste
- **AI Timesheet desktop app** — separate desktop app, complex, probably better to use Odoo's official one when out

---

## 🔁 Migration consideration

When Odoo 20 GA (Oct 2026):
- Test if Odoo native version replaces our custom one cleanly
- If yes: deprecate KOB module → switch to native
- If no: keep KOB module, port to Odoo 20 API

Build with **interfaces matching Odoo 20 spec** so swap-out is trivial. E.g., for Timesheet Timer use the same data model + button placement Odoo 20 will use.

---

## Key risks

1. **Building features Odoo 20 ships natively** — wasted effort, potential conflict on upgrade. Mitigate: design APIs identical to Odoo 20 spec.
2. **AI feature scope creep** — agent does too much, breaks user trust. Mitigate: strict tool whitelist, human-in-loop for writes.
3. **Read-replica complexity** — replication lag causes data inconsistency. Mitigate: lag monitor, fail-fast routing.

---

## Action: Pick top 3 to start

Recommend starting with **Phase 1** (3 quick wins, ~6 days total work):
1. Timesheet Timer (#1)
2. Polls in Discuss (#2)
3. Activity in Calendar (#3)

Each is ≤3 days, low-risk, user-visible. Build, ship, iterate.
