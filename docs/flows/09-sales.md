# 09 · sales — Customer / Sales Order / Delivery

## Reference

| | Path |
|-|------|
| Odoo 18 sale | `odoo-18.0\odoo\addons\sale\models\` (https://github.com/odoo/odoo/tree/18.0/addons/sale/models) |
| Odoo 18 sale_stock | `odoo-18.0\odoo\addons\sale_stock\models\` (https://github.com/odoo/odoo/tree/18.0/addons/sale_stock/models) |
| Odoo 19 sale | `odoo-19.0\addons\sale\` (https://github.com/odoo/odoo/tree/master/addons/sale) |

## KOB-ERP files

```
backend/modules/sales/
├── models.py        — Customer, SalesOrder, SoLine, Delivery, DeliveryLine
├── schemas.py
└── routes.py        — /api/v1/sales/*
```

## Data shape

```
sales.customer
  id, code (UNIQUE), name, tax_id, email, phone,
  billing_address, shipping_address, currency, payment_terms, active

sales.sales_order
  id, ref (UNIQUE), customer_id, ordered_date, expected_delivery_date,
  currency, state, total_amount

sales.so_line
  id, so_id, product_id, qty_ordered, qty_delivered, unit_price, line_total

sales.delivery
  id, ref, so_id, delivered_date, state ∈ {draft, validated},
  warehouse_id, courier_id

sales.delivery_line
  id, delivery_id, so_line_id, product_id, qty_delivered, lot_id
```

## State machine — SalesOrder

```
draft → quote → confirmed → in_progress → delivered → invoiced → closed   (terminal)
   ↓       ↓        ↓             ↓            ↓
   └───────┴────────┴─────────────┴────────────┴──→ cancelled            (terminal)
```

## Happy-path flow

```
1. (master)  POST /sales/customers
   { code: "C-LAZ-001", name: "ลูกค้า A", currency: "THB", payment_terms: "COD" }

2. POST /sales/sales-orders
   { ref: "SO-2026-0042", customer_id, ordered_date: today,
     expected_delivery_date: +2d, lines: [
       { product_id, qty_ordered: 2, unit_price: 590 }
     ] }
   ──> SalesOrder(state="draft")

3. POST /sales/sales-orders/{id}/transition?target=quote
   (sales rep sends quote to customer)

4. POST /sales/sales-orders/{id}/transition?target=confirmed
   (customer accepts)

5. (alternate path)  promote a platform order:
   ops.platform_order.outbound_order_id is set when an outbound.order is
   created from a platform order.  A scheduled job pairs that outbound order
   with a sales.sales_order so revenue lands in the right place.

6. POST /sales/sales-orders/{id}/transition?target=in_progress
   ── triggers an outbound.order via service.create_order_with_lines
   ── (today this link is documented but not auto-wired — Phase 4 follow-up)

7. POST /sales/deliveries
   { ref: "DEL-2026-0042", so_id, delivered_date, warehouse_id, courier_id,
     lines: [
       { so_line_id, product_id, qty_delivered: 2, lot_id }
     ] }
   ──> Delivery(state="draft")

8. POST /sales/deliveries/{id}/validate
   ── per line:
        so_line.qty_delivered += line.qty_delivered
        decrement inventory.stock_quant from warehouse stock loc
   ── if every so_line fully delivered: SO transitions to "delivered"

9. POST /sales/sales-orders/{id}/transition?target=invoiced
   (Phase 5 — creates an accounting.invoice and journal entry pair)

10. POST /sales/sales-orders/{id}/transition?target=closed
```

## SalesPage UI

The SalesPage shows aggregate metrics:

- Total revenue this month (sum of `total_amount` where `state` ∈
  {confirmed, in_progress, delivered, invoiced, closed})
- Customer grid (top customers by 90-day revenue)
- Order table with state badges + drill-into-form

## Hooks

- Confirming an SO **should** create a corresponding outbound.order so
  warehouse staff can pick.  Today the link is manual — Phase 4 follow-up
  to auto-wire via the event bus (`emit("sales.confirmed", {so_id})`).
- Validating a delivery decrements stock quants directly; same trade-off
  as `purchase.receipt` (see [07-purchase.md](07-purchase.md)).

## Differences vs Odoo

| | Odoo `sale.order` | KOB-ERP `sales.sales_order` |
|-|------|---------|
| Customer | `res.partner` | dedicated `sales.customer` table |
| Quote → Order | same model | same — single record progresses through `quote → confirmed` |
| Delivery | implicit via `stock.picking` of type "outgoing" | dedicated `sales.delivery` table linking to `sales.so_line` |
| Invoicing | tightly coupled (`account.move`) | placeholder — invoicing logic in Phase 5 |
| Multi-currency | full FX support | `currency` recorded; no live conversion yet |
