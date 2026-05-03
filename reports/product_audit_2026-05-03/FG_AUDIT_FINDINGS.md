# FG Audit Findings — 2026-05-03

**Scope**: Finished Goods ทั้งหมด (saleable + shared, `categ_id child_of 67`)
**Templates**: 627
**Variants**: 1,860
**Database**: kissgroupdatacenter.com (Production)

ใช้ผ่าน Chrome Extension + Odoo JSON-RPC โดย user `Sivaporn Thapjaroen (id=119)` เข้าได้ทั้ง 3 บริษัท

---

## 📊 ภาพรวม

| Metric                                            | Value          |
|---------------------------------------------------|---------------:|
| FG templates (saleable, shared)                   | **627**        |
| Variants ของ FG ทั้งหมด                            | **1,860**      |
| Variants ที่มี cost ใน ≥2 บริษัท                     |    845 (45%)   |
| Variants ที่ cost ต่างกัน >5% ข้ามบริษัท               | **319 (38%)**  |
| FG templates ที่ output VAT ครบ 3 บริษัท            | 608 (97%)      |
| FG templates ที่ไม่มี seller ในทั้ง 3 บริษัท           | 450 (72%) ⚠    |
| FG templates ที่ seller ครบ 3 บริษัท (intercompany ครบ) |  177 (28%)     |

---

## 🔍 Top 25 variants ที่ cost ต่างกันมากที่สุด

| code           | name (ตัด)                                   | KISS     | BTV      | CMN      | spread   |
|----------------|----------------------------------------------|---------:|---------:|---------:|---------:|
| GJR1000        | GOOD GOODS Jasmine Rice Harmony 1,000 ml     | 1,822.00 |     0.00 | 1,326.50 |   495.50 |
| MFSG500        | FRAGRANCE REFILL 500 ml                      |   590.00 |     0.00 |   936.74 |   346.74 |
| GJR-IPQ        | GG JASMINE RICE HARMONY (สำหรับ I Plus Q)    | 1,822.00 |     0.00 | 1,502.67 |   319.33 |
| GDR500         | GG Jasmine Rice Harmony EDP 500 ml           |   470.00 |     0.00 |   194.85 |   275.15 |
| GDSW100        | GG Reed Diffuser 100 ml (Sweet Water)        |   309.11 |     0.00 |    52.77 |   256.33 |
| GDPG100        | GG Reed Diffuser 100 ml (Pink Glow)          |   308.36 |     0.00 |    56.17 |   252.19 |
| GDJR100        | GG Reed Diffuser 100 ml (Jasmine)            |   285.40 |     0.00 |    36.60 |   248.80 |
| MFRC500        | FRAGRANCE REFILL 500 ml (variant)            |   590.00 |     0.00 |   825.80 |   235.80 |
| GPRH050        | GG Jasmine EDP 50 ml                         |   234.88 |     0.00 |    24.56 |   210.32 |
| ZTBJB1         | BUYDIDI Joybos Garbage Bag                   |   257.60 |    51.52 |     0.00 |   206.08 |
| MFMR500        | FRAGRANCE REFILL 500 ml (variant)            |   590.00 |     0.00 |   783.99 |   193.99 |
| GPRH030        | GG Jasmine EDP 30 ml                         |   184.34 |     0.00 |    13.21 |   171.12 |
| KPVD050        | KISS-MY-BODY EDP 50 ml                       |   155.89 |    92.75 |    13.68 |   142.21 |
| KPDD050        | KISS-MY-BODY EDP 50 ml                       |    81.66 |   127.82 |    11.15 |   116.67 |
| KPWF050        | KISS-MY-BODY EDP 50 ml                       |    95.44 |   127.82 |    14.92 |   112.90 |
| KPNN050        | KISS-MY-BODY EDP 50 ml                       |    98.61 |   130.96 |    23.35 |   107.61 |
| KPSS050        | KISS-MY-BODY EDP 50 ml                       |    95.44 |   127.82 |    21.28 |   106.54 |
| KAPV050        | KAYE Parfum 50 ml                            |   114.19 |     0.00 |    16.40 |    97.79 |
| KAPT050        | KAYE Parfum 50 ml                            |   114.19 |     0.00 |    17.68 |    96.51 |
| KPCL050-VN     | KISS-MY-BODY EDP 50 ml [VN]                  |   100.93 |     0.00 |    15.64 |    85.29 |
| KPCL050        | KISS-MY-BODY EDP 50 ml                       |    99.90 |    92.79 |    15.74 |    84.15 |
| KPGK050        | KISS-MY-BODY EDP 50 ml                       |   100.12 |    92.41 |    16.70 |    83.42 |
| KAPO050        | KAYE Parfum 50 ml                            |   114.59 |     0.00 |    31.38 |    83.21 |
| KPSS050-VN     | KISS-MY-BODY EDP 50 ml [VN]                  |    96.49 |     0.00 |    14.55 |    81.93 |
| KICM050        | KISS-MY-BODY EDP Intense 50 ml               |   105.12 |   106.79 |    25.38 |    81.41 |

---

## 💡 Pattern ที่สังเกตเห็น

### Pattern A — Three-tier cost (manufacturer → distributor → reseller)
```
CMN (ผลิต) ────► KISS (รับ + overhead) ────► BTV (รับจาก KISS)
   13-25 ฿            95-160 ฿                   90-130 ฿
```
ตัวอย่าง KPCL050: CMN=15.74 → KISS=99.90 → BTV=92.79 — **flow ปกติ ✓**

### Pattern B — BTV cost = 0 (BTV ไม่มีของ — ตามที่ user แจ้ง)
- GJR1000, MFSG500, GJR-IPQ, GDR500, GG Reed Diffuser ทั้งหมด, KAYE Parfum, KPCL050-VN/KPSS050-VN
- เหล่านี้ **ไม่ใช่ bug** — BTV ไม่ได้ขายในไทย/ไม่ทำ flow นี้

### Pattern C — KISS = 0, BTV หรือ CMN > 0 ⚠
- ZTBJB1 (BUYDIDI): KISS=257.60, BTV=51.52, **CMN=0** — น่าตรวจ (ทำไม CMN ไม่มี cost ทั้งที่ผลิต/ซื้อมา)

### Pattern D — KISS cost < CMN cost (gross margin ติดลบ?)
- MFSG500: KISS=590.00, CMN=936.74 — KISS รับมา 936.74 แต่ขายตัวเลขนี้คงงงๆ
- MFMR500: KISS=590.00, CMN=783.99
- MFRC500: KISS=590.00, CMN=825.80
- GPRH050: KISS=234.88, CMN=24.56 (ปกติ — markup สูง)

---

## ✅ จุดที่ดีอยู่แล้ว

1. **97% ของ FG templates มี Output VAT ครบ 3 บริษัท** (608/627) — UAT ผ่านได้เกือบทั้งหมด
2. **28% มี seller ใน 3 บริษัท** (177/627) — intercompany flow ใช้งานได้
3. **Cost ต่างกันต่อบริษัท** = ตามต้นทุนจริง (manufacturing vs intercompany pricing)

## ⚠️ จุดที่ควรตรวจ

| # | Issue                                          | Count  | Severity | Action                                        |
|---|------------------------------------------------|-------:|----------|-----------------------------------------------|
| 1 | FG ไม่มี seller ในบริษัทใดๆ                       |  450  | High     | ต้องเลือก vendor ทุกครั้งทำ PO — เพิ่มประสิทธิภาพ |
| 2 | FG ที่มี cost ต่างกันมาก แต่ไม่ใช่ pattern ปกติ        | ~10   | Medium   | ตรวจราย SKU (ZTBJB1, MFSG500 ฯลฯ)              |
| 3 | FG ที่ BTV เป็นแหล่งซื้อแต่ KISS ไม่มี cost (Pattern C) |  ~5  | Low      | ตรวจ KISS supplierinfo                         |
| 4 | output VAT ขาด (3 KISS, 6 BTV, 12 CMN)            |   21  | Low      | ถ้าจริงๆ บริษัทนั้นไม่ขาย → ปล่อยตามนี้                  |

---

## 📁 ไฟล์ในรอบนี้

| ไฟล์                                 | ขนาด     | คำอธิบาย                               |
|--------------------------------------|---------:|----------------------------------------|
| `AUDIT_SUMMARY.md`                   |    7 KB  | ภาพรวม 1,711 saleable+purchasable      |
| `UAT_DIAGRAM_KLC226.md`              |    8 KB  | KLC226 ใน 3 บริษัท + supplier flow     |
| `fg_audit_per_company.csv`           |  106 KB  | 627 FG templates × 3 บริษัท            |
| `FG_AUDIT_FINDINGS.md`               |   ~6 KB  | (รายงานนี้) ผลวิเคราะห์ FG variants 1,860 |

(ไฟล์ `fg_audit_variants.csv` 137 KB อยู่ในหน่วยความจำ browser แต่ Chrome block multi-download — ใช้ JS:
`copy(window._fgVariantCsv)` ใน DevTools เพื่อ copy ลง clipboard ได้)

---

## 🎯 ขั้นตอนต่อไปที่แนะนำ

1. **ตรวจ Pattern C / Pattern D variants** (~10-15 รายการ) — อาจเป็น data quality issue
2. **ตัดสินใจเรื่อง "no_seller" 450 รายการ**:
   - ถ้าซื้อจาก vendor เดิมเป็นประจำ → bulk ใส่ `seller_ids`
   - ถ้าเป็น service/internal → ปล่อยไว้
3. **ยืนยันว่า BTV cost=0 ใน FG ส่วนใหญ่ คือ intentional** (BTV ไม่ขาย) — ผ่าน UAT
4. **ผ่าน UAT แล้วค่อยพิจารณา**:
   - เขียน module `kob_intercompany_helper` เพื่อ enforce flow ที่ถูก
   - เพิ่ม cron audit ที่ flag products ที่ tax/seller mismatch กับ business intent
