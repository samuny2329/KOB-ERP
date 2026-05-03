# Product Audit Summary — 2026-05-03

**Database**: kissgroupdatacenter.com (Production)
**Scope**: Shared products (`company_id = False`) ที่ saleable + purchasable + active
**Total products in scope**: **1,711**
**Companies**: KISS (id=1) / BTV (id=2) / CMN (id=3)

---

## 1. Distribution by category (top 12)

| Category                                                       | Count |
|----------------------------------------------------------------|------:|
| Packaging / Packaging - Domestic                               |   383 |
| Finished Goods / Finished Goods - Domestic                     |   337 |
| Finished Goods / Finished Goods - Imported                     |   276 |
| Packaging / Packaging - Imported                               |   145 |
| Raw Materials / Raw Materials - Domestic                       |   109 |
| CMN-EXP / Production                                           |    95 |
| Expense / Administration Expenses / Staff Welfare Expense      |    37 |
| Expense / Administration Expenses / Financial Expense          |    27 |
| CMN-EXP / Warehouse                                            |    26 |
| Expense / Selling Expenses / Non-allocated Expenses / Warehouse |    24 |
| Expense / Administration Expenses / Management Office Expenses |    23 |
| Semi-Finished / Semi-Finished - Domestic                       |    19 |

> **สังเกต**: shared products มีทั้งสินค้าจริง (FG/Pack/RM) และ category Expense → category Expense ที่อยู่ใน shared products น่าตรวจ — น่าจะเป็น service/expense items ที่ทุกบริษัทต้องใช้ร่วมกัน

## 2. Type / Tracking

| Field    | Value     | Count |
|----------|-----------|------:|
| type     | consu     | 1,296 |
| type     | service   |   415 |
| tracking | lot       | 1,259 |
| tracking | none      |   452 |

> **ไม่มี product ที่ type='product' (storable)** ใน shared bucket — น่าจะเก็บ stock เฉพาะใน per-company products เท่านั้น

## 3. Routes — รวมเป็น 7 patterns

| route_ids (sorted)        | Meaning                          | Count |
|---------------------------|----------------------------------|------:|
| `7`                       | Buy only                         |   742 |
| `7,16`                    | Buy + Resupply Subcontractor on Order | 482 |
| `5,7,16`                  | Manufacture + Buy + Resupply     |   337 |
| `5,7`                     | Manufacture + Buy                |    98 |
| `5`                       | Manufacture only                 |    36 |
| `5,16`                    | Manufacture + Resupply           |    12 |
| `16`                      | Resupply only                    |     4 |

> **Routes ทั้งหมดเป็น global routes (company_id = False)** ไม่มี company-specific route ผูกที่ template — diagram ต่างกันต่อบริษัทเพราะ warehouse rules + category rules

## 4. Output VAT (taxes_id) — 8 patterns

| taxes_id           | Meaning                       | Count |
|--------------------|-------------------------------|------:|
| `2,20,38`          | KISS + BTV + CMN (full)       | 1,638 (95.7%) |
| `38`               | CMN only                      |    22 |
| `2,20`             | KISS + BTV (no CMN)           |    19 |
| `2`                | KISS only                     |    11 |
| `4,20,38`          | KISS 0% + BTV + CMN           |    10 |
| `2,38`             | KISS + CMN (no BTV) **← KLC226 อยู่กลุ่มนี้** | 8 |
| `20,38`            | BTV + CMN (no KISS)           |     2 |
| (empty)            |                               |     1 |

## 5. Input VAT (supplier_taxes_id) — 9 patterns

| supplier_taxes_id  | Count |
|--------------------|------:|
| `1,19,37`          | 1,606 (93.9%) |
| `3,19,37`          |    42 |
| `37`               |    22 |
| `1`                |    12 |
| `1,21,37`          |    12 |
| `1,19,39`          |    10 |
| `1,37`             |     4 |
| `1,19`             |     2 |
| `19,37`            |     1 |

## 6. ⚠️ Anomalies (need attention for UAT)

| Issue              | Count | % of 1,711 |
|--------------------|------:|----------:|
| ❌ ไม่มี seller_ids  |   718 |   42.0% |
| ⚠️ ไม่มี default_code |   487 |   28.5% |
| ⚠️ list_price = 0    |   672 |   39.3% |
| ✓ ไม่มี category    |     0 |    0.0% |

**42% ไม่มี vendor** — purchase orders จะต้องเลือก vendor ทุกครั้ง
**28.5% ไม่มี SKU code** — ใช้แค่ name อ้างอิง ทำให้ search/scan ลำบาก
**39% ราคาขาย 0** — ต้อง override ทุกครั้งที่ขาย

Sample anomalies (no_seller):
- `032-0000000065` Cap Bottle 1 Litre ฝาสีขาว [KSS]
- `033-0000000049` กล่อง Carton 446×446×195 mm. 1:36 JDR
- `033-0000000062` ลัง 1:48 377×497×181 ±3 mm. 100 ml. JDB
- `101707` MKT/GAE Advance payment-Others (อาจจงใจ — เป็น service)

---

## 7. ข้อเสนอ next steps สำหรับ UAT

### 7.1 Fix the 8 products in `2,38` (KLC226's group) ?
- ✗ **ไม่ต้อง** — user confirm ว่า BTV ไม่มีของพวกนี้, intercompany flow ใช้ supplierinfo (BTV←KISS) แทน

### 7.2 Add seller_ids to 718 products ?
- ✓ **ควรพิจารณา** — โดยเฉพาะ Packaging/RM/FG ที่ purchase_ok=True
- ต้องรู้ vendor ที่ตั้งใจ → ขอ master list จาก user หรือใช้ค่าจากประวัติ PO ย้อนหลัง

### 7.3 Generate UAT route diagram per (product × company) ?
- 1,711 × 3 = 5,133 diagrams — มากเกินคลิกผ่าน UI
- เสนอ: **เลือก sample 5-10 product/category** สำหรับ UAT, เปิด Routes Report ใน context ของแต่ละบริษัท
- ตัวอย่าง: KLC226 (Finished Goods Domestic), 1 ตัวจาก Packaging Domestic, 1 ตัวจาก Raw Materials, 1 service item

### 7.4 Standardize tax-set ให้สอดคล้องกับ business intent ?
- **8 products ใน `2,38`** = KISS+CMN ขาย, BTV ขายผ่าน intercompany → ปัจจุบันถูก
- **22 products ใน `38` only** = CMN-only sale → ตรวจว่าจริงไหม
- **11 products ใน `2` only** = KISS-only sale → ตรวจว่าจริงไหม

---

## 8. Files

- รายงานนี้: `AUDIT_SUMMARY.md`
- ข้อมูลดิบ: ยังไม่ได้ export (รออนุญาต download)
