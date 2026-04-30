# 02 · inventory — StockQuant / Transfer / TransferLine

## Reference

| | Path |
|-|------|
| Odoo 18 stock_quant | `odoo-18.0\odoo\addons\stock\models\stock_quant.py` (https://github.com/odoo/odoo/tree/18.0/addons/stock/models/stock_quant.py) |
| Odoo 18 stock_picking | `odoo-18.0\odoo\addons\stock\models\stock_picking.py` (https://github.com/odoo/odoo/tree/18.0/addons/stock/models/stock_picking.py) |
| Odoo 18 stock_move | `odoo-18.0\odoo\addons\stock\models\stock_move.py` (https://github.com/odoo/odoo/tree/18.0/addons/stock/models/stock_move.py) |
| Odoo 19 | `odoo-19.0\addons\stock\models\` (https://github.com/odoo/odoo/tree/master/addons/stock/models) |

## KOB-ERP files

```
backend/modules/inventory/
├── models.py            — StockQuant, TransferType, Transfer, TransferLine
├── service.py           — create_transfer_with_lines, confirm/done/cancel
├── schemas.py           — *Create / *Read
└── routes.py            — /api/v1/inventory/* + transition endpoints
```

## Data shape

```
inventory.stock_quant
  id, location_id, product_id, lot_id (nullable),
  quantity (Numeric 16,4), reserved_quantity
  UNIQUE(location_id, product_id, lot_id)
  available_quantity (computed property) = quantity − reserved_quantity

inventory.transfer_type
  id, warehouse_id, code (e.g. "WH/IN"), name,
  direction ∈ {inbound, outbound, internal},
  sequence_prefix, default_source_location_id, default_dest_location_id

inventory.transfer       (header — has WorkflowMixin)
  id, name (auto-generated "<prefix>/000123"), transfer_type_id,
  source_location_id, dest_location_id, origin (free-text),
  scheduled_date, done_date, note, state

inventory.transfer_line
  id, transfer_id, product_id, uom_id, lot_id,
  source_location_id (override), dest_location_id (override),
  quantity_demand, quantity_done
```

## State machine — Transfer

```
allowed_transitions = {
  "draft":     {"confirmed", "cancelled"},
  "confirmed": {"done", "cancelled"},
  "done":      set(),
  "cancelled": set(),
}
```

## Happy-path flow

```
1. POST /inventory/transfer-types   (one-time per warehouse + direction)
   { warehouse_id, code: "WH1/IN", direction: "inbound",
     sequence_prefix: "WH1IN", default_source_location_id: <supplier>,
     default_dest_location_id: <stock> }

2. POST /inventory/transfers
   { transfer_type_id, source_location_id, dest_location_id,
     origin: "PO-2026-0042",
     lines: [
       { product_id, uom_id, quantity_demand: 100, lot_id: ... }
     ] }
   ──>  Transfer(name="WH1IN/000001", state="draft")

3. POST /inventory/transfers/{id}/confirm
   ── service.confirm_transfer:
       ├── validate lines exist + qty > 0
       ├── transition draft → confirmed  (raises 409 on illegal)
       └── (Phase 2a doesn't reserve stock yet — TODO Phase 2c)

4. POST /inventory/transfers/{id}/done
   ── service.complete_transfer:
       ├── for each line:
       │     qty = quantity_done OR quantity_demand
       │     line.quantity_done = qty
       │     src = _quant_for(src_location, product, lot)
       │     dst = _quant_for(dst_location, product, lot)
       │     src.quantity -= qty
       │     dst.quantity += qty
       ├── transition confirmed → done
       └── transfer.done_date = now()

5. POST /inventory/transfers/{id}/cancel  (any non-terminal state)
```

## Stock-quant invariant

The view layer **must not** assume `quantity ≥ 0` — virtual locations
(supplier, customer, inventory, view) can hold negative balances by
design.  Only `usage='internal'` locations are constrained physically; we
don't enforce this in the DB on purpose so corrections work.

## Hooks

- `service.create_transfer_with_lines` writes a sequence row via simple
  `COUNT(*)` per type — fine up to ~100k transfers per type.  When that
  becomes a bottleneck, replace with a Postgres `SEQUENCE` per
  `transfer_type` and a name template like `<prefix>/{nextval:06d}`.
- Audit log captures the quant delta on `done` (before/after JSON).

## Differences vs Odoo

| | Odoo | KOB-ERP |
|-|------|---------|
| `stock.move` reservations | reservation routine + assigned state | not yet — direct quant updates on `done` |
| Backorder splitting | partial pickings split off backorders | not modelled — line-level qty done can be < demand, but no backorder entity created |
| Routes / pull rules | trigger downstream moves | n/a |
| Lot reservations | lot pinned at reservation time | lot recorded at move time only |
| Multi-step picking (receipt → input → stock) | configurable per warehouse | direct one-step flow |
