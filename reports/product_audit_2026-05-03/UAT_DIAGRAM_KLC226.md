# UAT Diagram — KLC226 ในบริบทของ 3 บริษัท

**Product**: `[KLC226] KISS-MY-BODY Bright & Shine Perfume Lotion 226 g (Crazy In Love)`
**ID**: product.product = 24313 / product.template = 15418
**Type**: Goods (consu) — Tracked by Lots
**Category**: Finished Goods / Finished Goods - Domestic
**Visibility**: Shared (`company_id = False`) — เห็นทุกบริษัท

---

## 1. ข้อมูลตามบริบทแต่ละบริษัท

| Field                    | KISS (co=1)              | BTV (co=2)               | CMN (co=3)                |
|--------------------------|--------------------------|--------------------------|---------------------------|
| **standard_price (cost)** | 35.643 ฿ (avg)          | 34.463 ฿                | **11.987 ฿** ⬇            |
| **list_price (sales)**   | 0.00 ฿                  | 0.00 ฿                  | 0.00 ฿                   |
| **categ_id**             | Finished Goods Domestic | Finished Goods Domestic | Finished Goods Domestic  |
| **type / tracking**      | consu / lot             | consu / lot             | consu / lot              |
| **route_ids (template)** | Buy + Manufacture       | Buy + Manufacture       | Buy + Manufacture        |
| **taxes_id (Output VAT)** | `2` 7% Output VAT       | **`[]` ว่าง** ⚠         | `38` 7% (Output)         |
| **supplier_taxes_id**    | `1` 7% Input VAT        | `19` 7% Input VAT        | `37` 7% (Input)          |
| **seller_ids count**     | 7 vendors visible       | 1 vendor                | 0 vendors                |
| **rules_visible**        | 52 rules                | 50 rules                | 12 rules                 |
| **warehouses**           | 19 (KOB-* + channels)   | 18 (BTV-* + channels)   | 3 (CMN-WH + KK#1 + N/A) |

> **standard_price** เป็น property field — ต่างกันได้แต่ละบริษัทตามต้นทุนจริง:
> CMN = ราคาผลิต (11.987 ฿) → KISS ซื้อจาก CMN 20.74 ฿ + overhead → cost รวม 35.643 ฿
> BTV ซื้อจาก KISS 34.463 ฿ → cost = 34.463 ฿

## 2. Supplier flow (intercompany)

```
                  ┌──────────────────┐
                  │   CMN (ผลิต)     │  cost: 11.99 ฿
                  │  ขายที่ 20.74 ฿  │
                  └────────┬─────────┘
                           │
                ────────── ▼ ──────────
                          KISS
                  cost: 35.64 ฿
                  ขายที่ 34.46 ฿
                  ┌────────┬─────────┐
                  ▼                  ▼
              [End user]            BTV
                              cost: 34.46 ฿
```

**supplierinfo records** (ตามที่ระบบบันทึก):

| ID    | context (co) | vendor (partner_id)         | price    | min_qty | seq | product_id     |
|-------|--------------|-----------------------------|----------|---------|-----|----------------|
| 4395  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 1   | KLL226 variant |
| 4497  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 2   | KLS226 variant |
| 4555  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 3   | KLA226 variant |
| 4556  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 4   | KLM226 variant |
| 5170  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 5   | KLP226 variant |
| 5171  | KISS (1)     | CMN partner (12130)         | 20.74    | 1       | 6   | KLC226 variant |
| **4741** | **BTV (2)** | **KISS company partner (1)** | **34.463** | 1   | 5   | (template-level, no variant) |
| 6772  | KISS (1)     | BTV company partner (7)     | 34.493   | 1       | 7   | (template-level, no variant) |

> **id=4741**: BTV ซื้อจาก KISS — flow หลักของ intercompany ✓
> **id=6772**: KISS ซื้อจาก BTV — flow ย้อนกลับ (อาจเป็น swap / กระเด็นของจาก BTV ↔ KISS)

## 3. ⚠️ UAT Issues / Anomalies ที่พบบน KLC226

| # | Issue                                              | Severity | คำอธิบาย                                                                        |
|---|----------------------------------------------------|----------|------------------------------------------------------------------------------|
| 1 | BTV taxes_id ว่าง (no Output VAT)                  | Medium   | BTV ไม่ได้ขายตรง → ใช้ intercompany. ถ้า BTV ออก SO ของ KLC226 → ไม่มี tax อัตโนมัติ |
| 2 | id=6772 supplierinfo (KISS ← BTV) ไม่มี product_id | Low      | template-level seller — variants อาจไม่ default แสดงเวลาทำ PO                   |
| 3 | id=4741 (BTV ← KISS) ไม่มี product_id              | Low      | เหมือนข้อ 2 — variants ไม่ inherit specific seller                              |
| 4 | list_price = 0 ทุกบริษัท                          | Low      | ราคาขายต้อง override ทุกครั้ง — อาจตั้งใจถ้ามี pricelist เป็นหลัก                    |

## 4. ✓ จุดที่ถูกต้องแล้ว

- ✓ Routes (Buy + Manufacture) เป็น global routes — ใช้ได้ทุกบริษัท
- ✓ Category (Finished Goods Domestic) เป็น shared — เห็นทุกบริษัท
- ✓ Tracking = lot — รักษา lot เดียวกันข้ามบริษัท
- ✓ Cost ต่างกันต่อบริษัทตามต้นทุนจริง — ไม่ใช่ bug
- ✓ KISS supplier = CMN, BTV supplier = KISS — chain ที่ถูกต้อง

## 5. Routes/Rules ที่ apply (per company)

### KISS context (52 rules visible)
- Global: Buy, Manufacture, Resupply Subcontractor on Order
- Per-warehouse: KOB-WH1/2/SHOPEE/BOXME, Consignment, Not Available
- Per-channel: Watson, Eve and Boy, Beautrium, Boots, Konvy, OR, Better Way, Beautycool, Multy Beauty, S.C.Infinite, SCommerce, Soonthareeya
- POS: Summer Sale 2026

### BTV context (50 rules visible)
- Global: Buy, Manufacture, Resupply
- Per-warehouse: BTV-WH1/2/SHOPEE/BOXME, Consignment, Not Available
- Per-channel: เหมือน KISS ทุกตัว

### CMN context (12 rules visible)
- Global: Buy, Manufacture, Resupply
- Per-warehouse: CMN-WH (3 steps), CMN-WH KK#1 (1 step), CMN Not Available

---

## 6. Template สำหรับ batch UAT (เลือก 1 product → ดูทุก company)

ใช้ pattern นี้กับ product อื่นๆ:

```
┌─ PRODUCT [code] [name] ───────────────────────────┐
│  category, type, tracking                        │
│  template route_ids                              │
├──────────┬──────────┬──────────┬─────────────────┤
│ Field    │ KISS     │ BTV      │ CMN             │
├──────────┼──────────┼──────────┼─────────────────┤
│ cost     │ x.xx     │ x.xx     │ x.xx            │
│ taxes    │ [ids]    │ [ids]    │ [ids]           │
│ s.taxes  │ [ids]    │ [ids]    │ [ids]           │
│ sellers  │ N        │ N        │ N               │
│ wh count │ N        │ N        │ N               │
└──────────┴──────────┴──────────┴─────────────────┘
```

ผมเขียน script ดึงข้อมูลแบบนี้ batch ได้ทันที — ขอ list product ที่อยากเช็ค (1, 5, 100, ทั้ง 1,711 ?)
