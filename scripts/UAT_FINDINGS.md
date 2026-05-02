# UAT (kissgroupdatacenter.com) — Read-only inspection 2026-05-02

Captured via Chrome extension RPC + screenshots, no edits.

## Companies (note: CMN id differs from local!)

| id | Name | Local id |
|---|---|---|
| 1 | บริษัท คิสออฟบิวตี้ จำกัด (KOB) | 1 ✓ |
| 2 | บริษัท บิวตี้วิลล์ จำกัด (BTV) | 2 ✓ |
| 3 | บริษัท คอสโมเนชั่น จำกัด (CMN) | **4** ✗ |

→ Local CMN sits at id=4 because of an aborted earlier install.  Remap
   needed if we want UAT-compatible exports.

## Sale Order Type (model `sale.order.type`)

The "Order Type" field on stock.picking + sale.order is provided by a
community addon (likely OCA `sale_order_type`).  Values in UAT:

| id | Name |
|---|---|
| 1 | Return Order |
| 2 | Sampling Order |
| 3 | Normal Order |  ← default for marketplace imports
| 4 | Consignment Order |
| 5 | Direct Return Order |
| 8 | Adj Inventory |
| 9 | Assets |

## Custom fields

### `stock.picking`
- `sale_order_type_id` → `sale.order.type` (the Order Type field shown on the form)
- `sale_order_type_name` (char)
- `x_kob_source_ref` → `utm.source`
- `x_kob_order_date_ref` (datetime)
- `x_kob_scheduled_date` (datetime)
- `x_kob_order_sn_ref` (char)
- `x_kob_fake_order` (boolean)
- `x_kob_products_availability` (char)
- `x_picking_ids_purchase_order_count` (integer)
- `x_studio_related_field_6cm_1ivhe3mva` (boolean) — Studio-generated

### `sale.order`
- `sale_order_type_id` → `sale.order.type`
- `sale_order_type_name` (char)
- `x_kob_total_discount_excl_vat` (monetary)
- `x_quotation_date` (datetime)
- `x_kob_amount_before_discount_exclude_vat` (monetary)
- `x_kob_products_availability_ref` (char)
- `x_kob_stock_picking_delivery_date` (datetime)
- `x_studio_invoice_date` (date) — Studio
- `x_kob_inv_preview` (char)
- `x_kob_invoice_number` → `account.move` (m2m)

### `product.template`
- `x_kob_brand` (char)
- `x_kob_product_category` (char)  ← we don't have this locally yet

## Operations Types — 87 total

Pattern per warehouse: Receipts, Storage, Delivery Orders,
Manufacturing, Resupply Subcontractor, Internal Transfers.

Each warehouse gets its own picking-type set keyed by warehouse code:

```
KOB-WH1 (Offline)  KOB-WH2 (Online)  KOB Consignment  KOB Not Avaliable
Watson  Beautrium  Beautycool  Better Way  Boots  Eve and Boy
Konvy  Multy Beauty  S.C.Infinite  SCommerce  Soonthareeya
Summer Sale 2026  KOB-SHOPEE  …
```

### Sample: KOB-WH2 (Online) Delivery Orders

```
Type of Operation     Delivery
Reference Sequence    KOB-WH2 (Online) Sequence out
Sequence Prefix       OUT
Warehouse             KOB-WH2 (Online)
Barcode               K-ONOUT
Reservation Method    At Confirmation
Source Location       K-On/Stock         ← (deliver path uses /Stock/PICKFACE)
Destination Location  Partners/Customers
Returns Type          KOB-WH2 (Online): Receipts
Create Backorder      Ask
Lots/Serial Use Existing Ones  ☑
```

## Routes — 46 total

Pattern: every warehouse has up to 5 routes:
1. `<WH>: Receive in N step (stock)`
2. `<WH>: Deliver in 1 step (ship)`
3. `<WH>: Cross-Dock`
4. `<WH>: Resupply Subcontractor`
5. `Replenish on Order (MTO)` (shared)

Plus group routes: Buy, Manufacture, Return to CL, Resupply Subcontractor on Order.

## Rules — 98 total

Pattern per warehouse (e.g. K-On / KOB-WH2):

| Action | Source | Dest | Route |
|---|---|---|---|
| Pull From | K-On/Stock/PICKFACE | Partners/Customers | KOB-WH2 (Online): Deliver in 1 step (ship) |
| Pull From | K-On/Input | K-On/Output | KOB-WH2 (Online): Cross-Dock |
| Pull From | K-On/Output | Partners/Customers | KOB-WH2 (Online): Cross-Dock |
| Pull From | K-On/Stock | Partners/Customers | Replenish on Order (MTO) |
| Buy       | K-On/Stock | (vendor)            | Buy |

The K-On warehouse uses **`K-On/Stock/PICKFACE`** as the pulling
source for delivery — confirms Notion's "real picking face" pattern.

## BOMs — 1156 total

Sample: `SMA025 (72 Unit)` — SKINOXY Mask, company_id=3 (CMN) — so
**Cosmonation owns the production BOMs**, KOB/BTV are downstream
distributors via subcontract / consignment routes.

## Pickface Locations

```
B-On/Stock/PICKFACE   (BTV online)
K-On/Stock/PICKFACE   (KOB online)
```

## Installed Add-ons relevant to KOB customisation

```
kiss_account_wht           — WHT certificate / accounting (CN/PND)
kiss_account_wht_report
kiss_payment_deposit_wht
rooba_account_wht          — alternate WHT addon family
rooba_account_wht_report
rooba_account_billing_note_wht
rooba_payment_deposit_wht
rooba_purchase_wht
rooba_sale_wht
studio_customization       — Odoo Studio applied changes
web_studio
website_studio
```

## Implications for local kobdb

1. Install / create `sale.order.type` model with the 7 values above.
2. Add `x_kob_product_category` (char) on `product.template`.
3. Decide whether to keep CMN id=4 locally or remap to id=3.
4. The `x_studio_*` fields are Studio-generated — replicate manually
   if needed.
5. Marketplace import wizard should default `sale_order_type_id` =
   `Normal Order` (id 3 in UAT, sequence-resolve in local).
