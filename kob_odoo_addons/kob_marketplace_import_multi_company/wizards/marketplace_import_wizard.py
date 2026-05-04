"""Multi-company validation override for the marketplace import wizard.

Hooks into action_import to:
  1. Resolve a "home company" per product (= company holding live stock).
  2. Group order lines by home company so each company gets its own SO.
  3. Skip + warn if a product has no stock in any allowed company.

Allowed companies:
  - If `restrict_to_active_companies` is on (default), use the user's
    company switcher (`self.env.companies`) — ie, only ticked companies.
  - Otherwise, all companies the user has access to are allowed.
"""

import logging
from collections import defaultdict

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MarketplaceImportWizard(models.TransientModel):
    _inherit = "kob.marketplace.import.wizard"

    enforce_product_company = fields.Boolean(
        string="Route SO by product company",
        default=True,
        help=(
            "When enabled, each order line is routed to the company that "
            "actually stocks the product. Orders with mixed-company lines "
            "are split into one SO per company. Products not stocked in "
            "any allowed company are skipped with a warning in the log."
        ),
    )
    restrict_to_active_companies = fields.Boolean(
        string="Use the company switcher",
        default=True,
        help=(
            "If on, only companies currently ticked in the user's company "
            "switcher are eligible to receive imported SOs. If off, every "
            "company the user has access to is eligible."
        ),
    )

    # ------------------------------------------------------------------
    # Home company resolution
    # ------------------------------------------------------------------

    def _kob_allowed_companies(self):
        if self.restrict_to_active_companies:
            return self.env.companies
        return self.env.user.company_ids

    def _kob_product_home_company(self, product, allowed_companies):
        """Return the company that 'owns' a product, restricted to
        allowed_companies. Strategy:

        1. If product.company_id is set and allowed → return it.
        2. Search stock.quant for on-hand qty per allowed company; pick
           the company with the highest qty.
        3. If no stock anywhere → return False (caller decides what to do).
        """
        Quant = self.env["stock.quant"].sudo()
        if product.company_id and product.company_id in allowed_companies:
            return product.company_id

        # Per-company stock totals (internal locations only)
        per_company = {}
        quants = Quant.read_group(
            domain=[
                ("product_id", "=", product.id),
                ("location_id.usage", "=", "internal"),
                ("company_id", "in", allowed_companies.ids),
            ],
            fields=["company_id", "quantity:sum"],
            groupby=["company_id"],
        )
        for row in quants:
            co_tuple = row.get("company_id")
            if not co_tuple:
                continue
            co_id = co_tuple[0] if isinstance(co_tuple, (list, tuple)) else co_tuple
            qty = row.get("quantity", 0) or 0
            if qty > 0:
                per_company[co_id] = qty

        if not per_company:
            return self.env["res.company"].browse()

        # Prefer wizard's primary company when it has stock
        if self.company_id and self.company_id.id in per_company:
            return self.company_id

        best_co_id = max(per_company, key=lambda cid: per_company[cid])
        return self.env["res.company"].browse(best_co_id)

    # ------------------------------------------------------------------
    # Hook into the product resolver — also returns home company
    # ------------------------------------------------------------------

    def _kob_resolve_with_company(self, sku, brand, allowed_companies):
        """Wrapper around _resolve_product that also returns the home
        company for the resolved product. Returns (product, company)."""
        product = self._resolve_product(sku, brand)
        if not product:
            return product, self.env["res.company"].browse()
        if not self.enforce_product_company:
            return product, self.company_id
        home = self._kob_product_home_company(product, allowed_companies)
        return product, home

    # ------------------------------------------------------------------
    # Override action_import
    # ------------------------------------------------------------------

    def action_import(self):
        """Re-implement the per-order SO creation loop with home-company
        routing. We delegate file parsing + product autocreate to the
        parent's helpers and only intercept the SO build phase."""
        if not self.enforce_product_company:
            return super().action_import()

        # The parent action_import does several things in one big method;
        # rather than copy-paste it, we let it run and post-process via
        # an overridable hook. Cleanest split is to monkey the per-order
        # vals construction. We mirror parent's flow but route per company.
        return self._kob_action_import_multi_company()

    def _kob_action_import_multi_company(self):
        """Fork of the parent action_import that splits SOs by product
        home company. We rely on parent helpers (_parse_blob,
        _resolve_product, _ensure_stock_with_lot, _normalize_date,
        _get_partner_for, _get_source) which remain unchanged."""
        from collections import defaultdict
        SaleOrder = self.env["sale.order"].sudo()
        sales = self.env["sale.order"]
        allowed = self._kob_allowed_companies()
        if not allowed:
            allowed = self.company_id

        # 1. Parse files (parent helper)
        rows = []
        if self.file_data:
            rows = self._parse_blob(
                self.file_data,
                self.file_name or "upload.xlsx",
                fallback_platform=self.platform,
            )
        for att in self.attachment_ids:
            rows += self._parse_blob(
                att.datas, att.name or "upload.xlsx",
                fallback_platform=self.platform,
            )

        if not rows:
            self.import_log = "No rows parsed from input."
            return self._reload_action()

        # 2. Group by (platform, order_sn) — same as parent
        by_order = defaultdict(list)
        for r in rows:
            by_order[(r["platform"], r["order_sn"])].append(r)

        log_lines = []
        fake_tag = self.env.ref(
            "kob_marketplace_import.tag_fake_order",
            raise_if_not_found=False,
        )

        # 3. Per-order, per-company SO creation
        for (platform, order_sn), lines in by_order.items():
            existing = SaleOrder.search(
                [("client_order_ref", "=", order_sn)], limit=1,
            )
            if existing:
                log_lines.append(
                    f"SKIP {order_sn} — already imported ({existing.name})"
                )
                continue

            partner = self._get_partner_for(platform) \
                if hasattr(self, "_get_partner_for") else self._partner_for(platform)
            head = lines[0]
            shop = head.get("shop") or "Unknown"
            source = self._get_source(shop) if hasattr(self, "_get_source") \
                else self._source_for(platform, shop)
            tag_ids = [(4, fake_tag.id)] if fake_tag and any(l.get("fake") for l in lines) else []

            # Group lines by resolved home company
            grouped = defaultdict(list)   # company_id (int) -> [line_vals]
            unresolved = []
            for ln in lines:
                product, home = self._kob_resolve_with_company(
                    ln["sku"], ln.get("brand"), allowed,
                )
                if not product:
                    unresolved.append(ln["sku"])
                    continue
                if not home:
                    log_lines.append(
                        f"⚠ {order_sn} — SKU '{ln['sku']}' has no stock in "
                        f"any allowed company ({', '.join(allowed.mapped('name'))}). "
                        f"Line skipped — assign stock first."
                    )
                    continue
                vals = {
                    "product_id": product.id,
                    "product_uom_qty": ln["qty"],
                }
                if ln.get("price"):
                    vals["price_unit"] = ln["price"]
                grouped[home.id].append((vals, ln, product))

            for sku in unresolved:
                log_lines.append(
                    f"WARN {order_sn} — SKU '{sku}' not found"
                )

            if not grouped:
                log_lines.append(
                    f"SKIP {order_sn} — all lines unresolved or no stock"
                )
                continue

            # Multi-company split: one SO per home company
            for company_id, line_pkgs in grouped.items():
                company = self.env["res.company"].browse(company_id)
                # Optional: stock seeding per-company
                if self.auto_adjust_lot:
                    target_wh = self.env["stock.warehouse"].search([
                        ("company_id", "=", company.id),
                    ], limit=1)
                    if target_wh:
                        for vals, ln, product in line_pkgs:
                            self.with_company(company)._ensure_stock_with_lot(
                                product,
                                float(ln.get("qty") or 0),
                                target_wh,
                                unit_cost=float(ln.get("price") or 0),
                                order_sn=order_sn,
                            )

                # Determine target warehouse for this company
                target_wh = self.env["stock.warehouse"].search([
                    ("company_id", "=", company.id),
                ], order="id", limit=1)
                # Fallback to wizard's warehouse if this company is the wizard's
                if company == self.company_id and self.warehouse_id:
                    target_wh = self.warehouse_id
                if not target_wh:
                    log_lines.append(
                        f"SKIP {order_sn} for {company.name} — no warehouse "
                        f"in that company. Configure one first."
                    )
                    continue

                # FBS auto-route (existing logic)
                if (getattr(self, "fbs_auto_route", False)
                    and platform == "shopee"
                    and order_sn.upper().endswith("-FBS")):
                    shopee_wh = self.env["stock.warehouse"].search([
                        ("company_id", "=", company.id),
                        ("name", "ilike", "SHOPEE"),
                    ], limit=1)
                    if shopee_wh:
                        target_wh = shopee_wh

                # Suffix the SO name when split so multiple SOs per
                # marketplace order_sn don't collide on `name`.
                so_name = str(order_sn).strip() or False
                if len(grouped) > 1 and so_name:
                    so_name = f"{so_name}-{company.name[:6]}"

                so_vals = {
                    "name": so_name,
                    "partner_id": partner.id,
                    "client_order_ref": order_sn,
                    "company_id": company.id,
                    "warehouse_id": target_wh.id,
                    "date_order": self._normalize_date(head["order_date"])
                                  if hasattr(self, "_normalize_date")
                                  else head["order_date"],
                    "source_id": source.id,
                    "tag_ids": tag_ids,
                    "order_line": [(0, 0, vals) for vals, _, _ in line_pkgs],
                }
                normal_type = self.env.ref(
                    "kob_marketplace_import.sale_order_type_normal",
                    raise_if_not_found=False,
                )
                if normal_type:
                    so_vals["sale_order_type_id"] = normal_type.id
                emarket_team = self.env["crm.team"].search(
                    [("name", "=", "eMarketplace")], limit=1,
                )
                if emarket_team:
                    so_vals["team_id"] = emarket_team.id

                try:
                    so = SaleOrder.with_company(company).create(so_vals)
                except Exception as e:
                    log_lines.append(
                        f"❌ {order_sn} → {company.name}: SO creation failed — {e}"
                    )
                    _logger.exception("SO creation failed for %s", order_sn)
                    continue
                sales |= so
                tag = "↪ routed" if company != self.company_id else "OK"
                log_lines.append(
                    f"{tag} {order_sn} → {company.name} → {so.name} "
                    f"({len(so.order_line)} lines)"
                )

                # Auto-confirm + assign (mirrors parent)
                if self.auto_confirm:
                    so.action_confirm()
                    if self.auto_assign:
                        for picking in so.picking_ids:
                            picking.action_assign()
                            picking.write({
                                "x_kob_source_ref": source.id,
                                "x_kob_order_date_ref": so.date_order,
                                "x_kob_fake_order": bool(tag_ids),
                            })

        self.import_log = "\n".join(log_lines) or "Nothing imported."
        return self._reload_action()

    def _reload_action(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
