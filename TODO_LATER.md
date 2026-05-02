# KOB ERP — Deferred Work

## 1. Help Tooltips (started, partial)

Goal: every column header / property has hover-tooltip with formula + benchmarks.

### Done
- ✅ `wms.worker.performance` (15 fields with formula + 🟢🟡🔴 ranges)
- ✅ `mfg.workcenter.oee` (10 fields with World-class benchmarks)

### Pending models to add `help="..."` to
- `kob.vendor.performance` — on_time_rate, fill_rate, quality_rate, price_stability, overall_score
- `kob.customer.ltv.snapshot` — revenue_90d, order_count_90d, avg_order_value, repeat_rate, return_rate, score
- `kob.fixed.asset` — acquisition_cost, salvage_value, useful_life_months, accumulated_depreciation, book_value
- `kob.intercompany.loan` — principal, interest_rate_pct, term_months, outstanding_balance
- `kob.procurement.budget` — total_budget, committed_amount, spent_amount, remaining_amount
- `stock.cycle.count.rule` — periodic_count_period, periodic_qty_per_period, accuracy_threshold
- `stock.inventory` — inventory_accuracy, exclude_sublocation, prefill_counted_quantity
- `stock.quant` — discrepancy_percent, discrepancy_threshold, has_over_discrepancy
- `kob.return.order` — refund_amount, reason_code (per-line)
- `kob.cost.allocation` — basis, share_pct, amount
- `wms.kpi.assessment` — final_score, grade, pillars
- `kob.pnd.filing` — filing_type, total_gross_wage, total_wht
- `kob.vat.period` — output_vat, input_vat, net_payable, form_type (PP30/PP36)
- `kob.fx.revaluation` — gain_loss
- `kob.wht.certificate` — wht_amount, wht_rate_pct
- `mrp.bom` — product_qty, type (normal/kit/subcontract)
- `purchase.order` — qty_received, qty_invoiced (3-way matching)

### Pattern

```python
field = fields.Float(
    string='Display Name',
    help="What it is. Formula: a / b × 100. "
         "Industry benchmark / KOB target. "
         "🟢 ≥X excellent · 🟡 X–Y OK · 🔴 <Y review.",
)
```

## 2. OCA Phase 3 — Reporting

Already cloned + version-patched, **NOT YET INSTALLED**:
- `account_financial_report` (Statement Reports: BS / P&L / Cash Flow / Trial Balance)

Likely install steps:
- Patch manifest version 18.0 → 19.0
- Strip `category_id` from security XML if present
- Strip `<group expand=...>` from search views
- Patch `name_search` signature (args → domain) on any product/account inherits
- `users` → `user_ids` on res.groups
- Test install + iterate

## 3. Bin location structure

User wants stock physically distributed only under PICKFACE for KOB-WH2.
Currently 1,578 quants in PICKFACE descendants ✅.
- **Putaway rules** — not yet configured (incoming receipts auto-route to bins)
- **Storage Categories** — not yet defined (size/weight constraints)
- **Removal Strategy override** — already FEFO globally

## 4. UAT data sync

- **Product cost from UAT** — partial (1,935 of 5,024 had standard_price > 0; current local uses 0.35 × list_price placeholder)
- **Product master refresh** — fresh data via Chrome MCP would override placeholder costs

## 5. Front-end issues

- `Valuation` menu visibility — added but user reports still not seeing it (likely cache)
- Datetime format DD/MM/YYYY HH:MM:SS — JS patch installed, requires hard reload/incognito

## 6. Other
- Check Availability button always visible on stock.picking — DONE
- Multi-step pull rule chain (PICKFACE → child) — DONE via parent_path search
