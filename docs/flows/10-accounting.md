# 10 · accounting — Chart of Accounts / Journal / Journal Entry / Tax

## Reference

| | Path |
|-|------|
| Odoo 18 account | `odoo-18.0\odoo\addons\account\models\` (https://github.com/odoo/odoo/tree/18.0/addons/account/models) |
| Odoo 19 account | `odoo-19.0\addons\account\` (https://github.com/odoo/odoo/tree/master/addons/account) |

## KOB-ERP files

```
backend/modules/accounting/
├── models.py        — Account, Journal, JournalEntry, JournalEntryLine, TaxRate
├── schemas.py
└── routes.py        — /api/v1/accounting/*
```

## Data shape

```
accounting.account             (Chart of Accounts — tree)
  id, code (UNIQUE), name, type ∈ ACCOUNT_TYPES,
  parent_id (tree), is_reconcilable, currency, active
ACCOUNT_TYPES = (asset, liability, equity, income, expense, off_balance)

accounting.journal
  id, code (UNIQUE), name, type ∈ {sale, purchase, bank, cash, general},
  default_account_id, currency, active

accounting.journal_entry        (the document)
  id, ref (UNIQUE), journal_id, posting_date, narration,
  state ∈ {draft, posted, cancelled}, total_debit, total_credit

accounting.journal_entry_line
  id, entry_id, account_id, partner_label,
  debit (Numeric 18,2), credit (Numeric 18,2), name,
  CHECK (debit ≥ 0 AND credit ≥ 0 AND NOT (debit > 0 AND credit > 0))

accounting.tax_rate
  id, code (UNIQUE), name, rate_pct, account_id (where the tax lands)
```

## Double-entry invariant

Every `journal_entry` must satisfy:

```
total_debit == total_credit
total_debit > 0
```

Enforced **on create** in `routes.py::create_journal_entry`:

```python
debit_total = sum(l.debit for l in body.lines)
credit_total = sum(l.credit for l in body.lines)
if debit_total != credit_total or debit_total == 0:
    raise HTTPException(400, "entry must be balanced and non-zero")
```

The constraint `NOT (debit > 0 AND credit > 0)` on each line forbids
"debit-and-credit on the same row" sloppiness.

## State machine — JournalEntry

```
draft → posted     (terminal — once posted, it's immutable)
   ↓
   └──→ cancelled  (terminal)
```

A `posted` entry cannot be edited.  Reversal pattern: post a new entry
that reverses the original (debit ↔ credit).

## Happy-path flow

```
1. (master) Seed Chart of Accounts:
   POST /accounting/accounts  { code: "1000", name: "Assets", type: "asset" }
   POST /accounting/accounts  { code: "1100", name: "Cash", type: "asset", parent_id: <1000> }
   POST /accounting/accounts  { code: "4000", name: "Sales Revenue", type: "income" }
   ... etc.

2. (master) Seed journals:
   POST /accounting/journals  { code: "SAL", name: "Sales Journal", type: "sale", default_account_id: <4000> }
   POST /accounting/journals  { code: "PUR", name: "Purchase Journal", type: "purchase" }
   POST /accounting/journals  { code: "BNK", name: "Bank Journal", type: "bank" }

3. POST /accounting/journal-entries
   { ref: "JE-2026-0042", journal_id: <SAL>, posting_date: today,
     narration: "Cash sale SO-1042",
     lines: [
       { account_id: <1100 Cash>,         debit: 1180, credit: 0 },
       { account_id: <4000 Sales>,        debit: 0,    credit: 1100 },
       { account_id: <2150 VAT Payable>,  debit: 0,    credit: 80  }
     ] }
   ── server validates debit_total == credit_total == 1180
   ──> JournalEntry(state="draft", total_debit=1180, total_credit=1180)

4. POST /accounting/journal-entries/{id}/transition?target=posted
   ── snapshot becomes immutable
   ── append_activity("accounting.entry.posted")
```

## AccountingPage UI

- Chart of Accounts table grouped by type.
- Journal Entry list with debit/credit totals + state badge.
- Drill into entry → see all lines + invariant check.

## Hooks (planned)

- Sales / Purchase events should fire automatic JE creation:
  - On `sales.sales_order` posted to `delivered`: create JE in Sales journal.
  - On `purchase.purchase_order` posted to `received`: create JE in Purchase
    journal.
  - On `mfg.subcon_recon` approved with `total_diff > 0`: create JE writing
    off the loss (`account_inventory_loss`).

These hooks are documented but not auto-wired yet — see TODO in
`backend/modules/accounting/service.py`.

## Differences vs Odoo

| | Odoo `account.move` | KOB-ERP `accounting.journal_entry` |
|-|------|---------|
| Move types | invoice / refund / move / receipt / etc | only "general" entries — invoicing logic to be added on top |
| Reconciliation | `account.move.line.reconcile` engine | not yet — `is_reconcilable` flag exists; engine is Phase 5 polish |
| Multi-currency | full FX with `res.currency` rates | currency stored per entry; no FX engine yet |
| Analytic accounting | `account.analytic.account` separate ledger | not modelled |
| Tax engine | sophisticated (`account.tax` w/ children, scopes) | flat `tax_rate` table — line-level tax is computed at the call site |
