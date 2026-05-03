# UAT Warehouse / Subcontract Context — 2026-05-03

**Source**: `https://odoo-uat.kissgroupbim.work` (database: `kiss-production_2026-03-09`)
**Read by**: Administrator (uid=2) via Chrome Extension RPC
**Purpose**: Reference snapshot of correct configuration for warehouses,
subcontracting, locations. Use this to align local `kobdb` (Odoo 19).

---

## 1. Companies (11 active)

| id | Name | Partner |
|---:|---|---:|
| 1 | บริษัท คิสออฟบิวตี้ จำกัด (KISS) | 1 |
| 2 | บริษัท บิวตี้วิลล์ จำกัด (BTV) | 7 |
| 3 | บริษัท คอสโมเนชั่น จำกัด (CMN) | 8 |
| 4 | KISS OF LIFE CO.,LTD. | 7707 |
| 5 | บริษัท บีกรุ้ปเวนเจอร์ | 2984 |
| 6 | บริษัท นีโอไจแอนท์ไบโอ | 2969 |
| 7 | บริษัท คิส เวนเจอร์ | 12818 |
| 8 | บริษัท บรอนสัน ไลฟ์ | 12819 |
| 9 | บริษัท บีแอนด์บี โฮลดิ้ง | 12820 |
| 10 | บริษัท เคที อินเตอร์ แลบ - KT | 12905 |
| 12 | บริษัท ยูม่า | 14947 |

> **Note**: kobdb has 3 companies (1=KISS, 2=BTV, **4=CMN** — id mismatch with UAT)

## 2. KISS Warehouses (UAT)

**Critical**: `resupply_wh_ids = [] (EMPTY)` for ALL warehouses. UAT does NOT chain warehouses.

| seq | code | name | reception | delivery |
|---:|---|---|---|---|
| 0 | **K-Off** | KOB-WH1 (Offline) | **two_steps** | ship_only |
| 1 | K-On | KOB-WH2 (Online) | one_step | ship_only |
| 2 | K-SPE | KOB-SHOPEE | one_step | ship_only |
| 3 | K-BOX | KOB-BOXME | one_step | ship_only |
| 4 | KCON | KOB Consignment | one_step | ship_only |
| 5 | KNOT | KOB Not Avaliable | one_step | ship_only |
| 6 | KC-WS | Watson | one_step | ship_only |
| 7 | KC-EB | Eve and Boy | one_step | ship_only |
| 8 | KC-BT | Beautrium | one_step | ship_only |
| 9 | KC-BO | Boots | one_step | ship_only |
| 10 | KC-OR | OR Health & Wellness | one_step | ship_only |
| 10 | KC-KV | Konvy | one_step | ship_only |
| 11 | KC-BW | Better Way | one_step | ship_only |
| 12 | KC-BC | Beautycool | one_step | ship_only |
| 13 | KC-MB | Multy Beauty | one_step | ship_only |
| 14 | KC-SC | S.C.Infinite | one_step | ship_only |
| 15 | KC-SM | SCommerce | one_step | ship_only |
| 16 | KC-SY | Soonthareeya | one_step | ship_only |
| 17 | K-POS | End Year Sale 2025 | one_step | ship_only |

## 3. BTV / CMN Main Warehouses

| Company | Code | Name | reception_steps |
|---|---|---|---|
| BTV | **B-Off** | BTV-WH1 (Offline) | **three_steps** ⚠ (not two!) |
| CMN | **CMNW** | CMN-WH | **three_steps** ⚠ |

## 4. Subcontracting Locations

**All under shared `Physical Locations` view (id=1)**:

| id | complete_name | company |
|---:|---|---|
| 46 | Physical Locations/Subcontracting Location | KISS (1) |
| 47 | Physical Locations/Subcontracting Location | BTV (2) |
| 48 | Physical Locations/Subcontracting Location | CMN (3) |
| 5815 | Physical Locations/Subcontracting Location | KISS OF LIFE (4) |
| 5828 | ... | บีกรุ้ปเวนเจอร์ (5) |
| 5841 | ... | นีโอไจแอนท์ไบโอ (6) |
| 5854 | ... | คิส เวนเจอร์ (7) |
| 5867 | ... | บรอนสัน ไลฟ์ (8) |
| 5880 | ... | บีแอนด์บี โฮลดิ้ง (9) |
| 5908 | ... | KT INTER LAB (10) |
| 6212 | ... | ยูม่า (12) |

> **Pattern**: each company has its own subcontracting location named "Subcontracting Location" parented to shared "Physical Locations" view (id=1)

## 5. Subcontractor Partners (UAT)

| id | name | company | is_subcontractor | sub loc |
|---:|---|---|---|---|
| 12130 | บริษัท คอสโมเนชั่น จำกัด | shared | True (per company) | Physical Locations/Subcontracting Location (per company) |
| 10672 | Cosmonation Co.,Ltd (00001) | CMN (3) | True | (CMN context) |
| 14029 | SHANGHAI PNC BIOTECH CO.,LTD. | KISS (1) | True | (KISS context) |
| 13881 | บริษัท คอสโมเนชั่น จำกัด (สาขาบางปู) | shared | True (per company) | (per company) |

> **CMN partner (12130)** is the main subcontractor for KISS/BTV. Property `property_stock_subcontractor` resolves per company to that company's own "Physical Locations/Subcontracting Location"

## 6. product_selectable=True Routes (UAT — only 6!)

| id | name | company |
|---:|---|---|
| 7 | Buy | shared |
| 267 | Return to CL | shared |
| 5 | Manufacture | shared |
| 16 | Resupply Subcontractor on Order | shared |
| 95 | Make to MO | CMN (3) |
| **17** | **KOB-WH1 (Offline): Resupply Subcontractor** | **KISS (1)** |

> **Key insight**: Of all the per-warehouse "Resupply Subcontractor" routes, ONLY `KOB-WH1: Resupply Subcontractor` is `product_selectable=True` for KISS. Other per-warehouse subcontract routes exist (active) but are not selectable on products.

## 7. Active subcontract routes (per-warehouse, all active=True even if not selectable)

| id | name | company | selectable |
|---:|---|---|---|
| 17 | KOB-WH1 (Offline): Resupply Subcontractor | KISS | **True** ⭐ |
| 96 | KOB-WH1 (Offline): Resupply Subcontractor (dup?) | KISS | False |
| 59 | KOB-WH2 (Online): Resupply Subcontractor | KISS | False |
| 18 | BTV-WH1 (Offline): Resupply Subcontractor | BTV | False |
| 54 | BTV-WH2 (Online): Resupply Subcontractor | BTV | False |
| 19 | CMN-WH: Resupply Subcontractor | CMN | False |
| 186 | Soonthareeya: Resupply Subcontractor | KISS | False |
| 101-131 | (other companies' subcontract routes) | various | False |
| 16 | Resupply Subcontractor on Order | shared | **True** ⭐ |

---

## 8. Implications for kobdb (local) alignment

| What I changed earlier on kobdb | UAT actual | Action |
|---|---|---|
| `resupply_wh_ids = K-Off` on 18+17 BTV/KISS WHs | `[]` empty | **REVERT** |
| Deactivated 37 per-warehouse subcontract routes | All active | **REVERT** (set active=True) |
| product_selectable on 15+ subcontract routes | Only KOB-WH1 | **REDUCE** (keep only K-Off equivalent) |
| K-Off seq=1, K-On seq=2 | K-Off=0, K-On=1 | **ADJUST** |
| Subcontracting parent = (none) | Physical Locations view | **CREATE** Physical Locations view + reparent |
| B-Off reception=one_step | three_steps | **CHANGE** |
| CMN-WH reception=one_step | three_steps | **CHANGE** |
| CMN partner is_subcontractor=False | True (per company) | **SET** per company |

## 9. Recommended action plan

1. Revert resupply_wh_ids changes (clear all)
2. Reactivate the 37 deactivated subcontract routes
3. Reduce product_selectable on subcontract routes — keep only `KOB-WH1 (Offline): Resupply Subcontractor` selectable
4. Set K-Off sequence=0
5. Set B-Off + CMN-WH reception_steps=three_steps
6. Create shared "Physical Locations" view (Odoo standard usually has this — may need to find/create)
7. Reparent Subcontracting locations under Physical Locations + rename to "Subcontracting Location"
8. Set CMN partner (id=75 on kobdb) is_subcontractor=True per company context (KISS/BTV)

## 10. Caveats

- **Subcontracting location** rename + reparent will fail due to mrp_subcontracting constraint `_check_subcontracting_location` (encountered earlier)
- **is_subcontractor write** previously didn't persist on kobdb — may be a related/computed field requiring specific setup (e.g., partner.subcontracting_location)

---

**Snapshot taken**: 2026-05-03 12:30 UTC
**By**: Administrator (UAT) via Chrome Extension JSON-RPC
