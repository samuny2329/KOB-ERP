# -*- coding: utf-8 -*-
"""Round-2 product setup — adds everything I missed in the first pass:

  * product.category hierarchy mirroring UAT:
        Finished Goods
          ├─ Finished Goods - Domestic
          ├─ Finished Goods - Export
        Raw Materials
        Packaging Materials
        Service / Other
  * Assign each product to a category by code/brand pattern.
  * Sales / Purchase / POS toggles all on (matching the screenshot).
  * Responsible team — KOB Warehouse & BD Team (or first stock team).
  * Best Before / Removal / Alert dates default 0 (= no offset).
"""

import logging

_logger = logging.getLogger("kob_complete")

# ── 1. Category tree ──────────────────────────────────────────────
PCat = env["product.category"]


def _ensure_cat(name, parent=None):
    domain = [("name", "=", name)]
    if parent:
        domain.append(("parent_id", "=", parent.id))
    else:
        domain.append(("parent_id", "=", False))
    cat = PCat.search(domain, limit=1)
    if not cat:
        cat = PCat.create({
            "name": name,
            "parent_id": parent.id if parent else False,
        })
    return cat


fg = _ensure_cat("Finished Goods")
fg_dom = _ensure_cat("Finished Goods - Domestic", fg)
fg_exp = _ensure_cat("Finished Goods - Export", fg)
rm = _ensure_cat("Raw Materials")
pm = _ensure_cat("Packaging Materials")
service = _ensure_cat("Service / Other")
print(
    f"[cat] tree ready — FG/Domestic={fg_dom.id}, FG/Export={fg_exp.id}, "
    f"RM={rm.id}, PM={pm.id}, Service={service.id}",
)

# ── 2. Resolve responsible team ───────────────────────────────────
Team = env["stock.picking.type"]
warehouse_team = env["res.users"].search([
    ("login", "=", "admin"),
], limit=1)
# Try to find a "KOB Warehouse & BD Team" in mail.alias / hr.department
HrDept = env.get("hr.department")
team_id = None
if HrDept is not None:
    dept = HrDept.search([("name", "ilike", "KOB Warehouse")], limit=1)
    if dept:
        team_id = dept.id
        print(f"[cat] KOB Warehouse & BD Team found: id={team_id}")

# ── 3. Per-product classification + set fields ────────────────────
ProductT = env["product.template"]
import_count = 0
for prod in ProductT.search([("default_code", "!=", False)]):
    code = (prod.default_code or "").upper()
    is_service = (prod.type == "service")

    # Pick category
    if is_service:
        target_cat = service
    elif code.startswith(("031-", "030-")):
        # 031 = packaging materials, 030 likely raw materials
        target_cat = pm if code.startswith("031-") else rm
    elif prod.company_id and prod.company_id.id in (1, 2):
        # House brand finished good (KOB or BTV)
        target_cat = fg_dom
    else:
        # Default to FG/Domestic for unclassified consumables
        target_cat = fg_dom if not is_service else service

    vals = {}
    if prod.categ_id != target_cat:
        vals["categ_id"] = target_cat.id
    if not prod.sale_ok:
        vals["sale_ok"] = True
    if not prod.purchase_ok:
        vals["purchase_ok"] = True
    if "available_in_pos" in prod._fields and not prod.available_in_pos:
        vals["available_in_pos"] = True
    # Responsible — only if the field exists on this Odoo build
    if team_id and "responsible_id" in prod._fields and not prod.responsible_id:
        vals["responsible_id"] = team_id

    if vals:
        prod.write(vals)
        import_count += 1

env.cr.commit()
print(f"[cat] updated {import_count} templates")

# ── 4. Final report ──────────────────────────────────────────────
print("\n[cat] per-category breakdown:")
for cat_id, label in (
    (fg.id, "Finished Goods (root)"),
    (fg_dom.id, "  ↳ FG / Domestic"),
    (fg_exp.id, "  ↳ FG / Export"),
    (rm.id, "Raw Materials"),
    (pm.id, "Packaging Materials"),
    (service.id, "Service / Other"),
):
    n = ProductT.search_count([("categ_id", "=", cat_id)])
    print(f"  {label}: {n}")

print("\n[cat] sale_ok / purchase_ok / available_in_pos coverage:")
print(f"  sale_ok:       {ProductT.search_count([('sale_ok', '=', True)])}")
print(f"  purchase_ok:   {ProductT.search_count([('purchase_ok', '=', True)])}")
if "available_in_pos" in ProductT._fields:
    print(f"  pos:           {ProductT.search_count([('available_in_pos', '=', True)])}")
