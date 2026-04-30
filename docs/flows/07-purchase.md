# 07 · purchase — Vendor / PO / Receipt

## Reference

| | Path |
|-|------|
| Odoo 18 purchase | `odoo-18.0\odoo\addons\purchase\models\` (https://github.com/odoo/odoo/tree/18.0/addons/purchase/models) |
| Odoo 18 purchase_stock | `odoo-18.0\odoo\addons\purchase_stock\models\` (https://github.com/odoo/odoo/tree/18.0/addons/purchase_stock/models) |
| Odoo 19 purchase | `odoo-19.0\addons\purchase\` (https://github.com/odoo/odoo/tree/master/addons/purchase) |

## KOB-ERP files

```
backend/modules/purchase/
├── models.py        — Vendor, PurchaseOrder, POLine, Receipt, ReceiptLine
├── schemas.py
└── routes.py        — /api/v1/purchase/*
```

## Data shape

```
purchase.vendor
  id, code (UNIQUE), name, tax_id, contact_name, phone, email, address,
  payment_terms, lead_days, active

purchase.purchase_order
  id, ref (UNIQUE), vendor_id, ordered_date, expected_date, currency,
  state, total_amount

purchase.po_line
  id, po_id, product_id, qty_ordered, qty_received, unit_price, line_total

purchase.receipt
  id, ref, po_id, received_date, state ∈ {draft, validated},
  warehouse_id (where stock will land)

purchase.receipt_line
  id, receipt_id, po_line_id, product_id, qty_received, lot_id
```

## State machine — PurchaseOrder

```
draft → sent → confirmed → received → invoiced → closed   (terminal)
   ↓       ↓        ↓          ↓
   └───────┴────────┴──────────┴──→ cancelled            (terminal)
```

## Happy-path flow

```
1. (master)  POST /purchase/vendors
   { code: "V-FACT-01", name: "Factory A", tax_id: "0107...", payment_terms: "NET30" }

2. POST /purchase/purchase-orders
   { ref: "PO-2026-0042", vendor_id, ordered_date: today, expected_date: +7d,
     currency: "THB", lines: [
       { product_id, qty_ordered: 1000, unit_price: 18 }
     ] }
   ──> PurchaseOrder(state="draft")
       po.total_amount = sum(line.qty_ordered × line.unit_price)

3. POST /purchase/purchase-orders/{id}/transition?target=sent
   ── e-mail / portal trigger lives outside this service (subscriber on event bus)

4. POST /purchase/purchase-orders/{id}/transition?target=confirmed
   ── ready to receive stock

5. POST /purchase/receipts
   { ref: "RCP-2026-0042", po_id, received_date, warehouse_id,
     lines: [
       { po_line_id, product_id, qty_received: 1000, lot_id }
     ] }
   ──> Receipt(state="draft")
       (no stock movement yet)

6. POST /purchase/receipts/{id}/validate
   ── per line:
        po_line.qty_received += line.qty_received
        increment inventory.stock_quant for (warehouse stock loc, product, lot)
   ── if every po_line is fully received: PO transitions to "received"

7. POST /purchase/purchase-orders/{id}/transition?target=invoiced
   (placeholder — accounting integration is Phase 5)

8. POST /purchase/purchase-orders/{id}/transition?target=closed
```

## 3-way match (planned, not yet enforced)

For each PO:

| Source A | Source B | Source C |
|----------|----------|----------|
| `po.qty_ordered` | `receipt.qty_received` | accounting.invoice_line.qty (Phase 5) |

A line passes 3-way match when **A == B == C** within tolerance (default 2%).
The check should run when a PO transitions to `closed`; tolerance lives on
the vendor (`purchase.vendor.match_tolerance_pct`, to be added).  Today the
guard is documented but not enforced.

## Hooks

- Stock quants are bumped by `validate_receipt` directly via the inventory
  service to keep `purchase` decoupled from `inventory.transfer` for now.
  When we want full traceability (Phase 3 follow-up), we'll instead create
  an `inventory.transfer` of type "WH/IN" and let its `done` action update
  quants — same outcome, audit-friendlier.

## Differences vs Odoo

| | Odoo `purchase.order` | KOB-ERP |
|-|------|---------|
| Vendor model | `res.partner` with `supplier_rank > 0` | dedicated `purchase.vendor` table |
| RFQ vs PO | both states on the same model | only PO; RFQ flow not modelled |
| Backorder | Odoo splits a receipt into a backorder picking | manual partial qty_received per line; no backorder entity |
| Multi-currency | `res.currency` + rate engine | currency as 3-letter string per PO; conversion deferred to accounting |
