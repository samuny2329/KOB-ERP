"""Multi-company validation + shop-name routing for marketplace imports.

Phase 1: validate product company on resolve (`enforce_product_company`).
Phase 2: route each marketplace order to the company configured in
         `wms.shop.company.map` based on its shop name. Falls back to
         the wizard's primary company if no mapping exists.
"""

import base64
import logging
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Re-import parent's module-level constants so the routed import flow
# can build partner / source records the same way the parent does.
try:
    from odoo.addons.kob_marketplace_import.wizards.marketplace_import_wizard \
        import _PARTNER_BY_PLATFORM, _PRETTY  # type: ignore
except Exception:  # pragma: no cover - install order safety
    _PARTNER_BY_PLATFORM = {
        "shopee": "Shopee Customer", "lazada": "Lazada Customer",
        "tiktok": "TikTok Customer", "odoo": "Odoo Customer",
        "pos": "POS Customer", "manual": "Manual Customer",
    }
    _PRETTY = {
        "shopee": "Shopee", "lazada": "Lazada", "tiktok": "TikTok",
        "odoo": "Odoo", "pos": "POS", "manual": "Manual",
    }


class MarketplaceImportWizard(models.TransientModel):
    _inherit = "kob.marketplace.import.wizard"

    enforce_product_company = fields.Boolean(
        string="Skip products not stocked in this company",
        default=True,
        help=(
            "When enabled, only SKUs that actually have on-hand stock in "
            "the selected company (or in any active-switcher company if "
            "'Use the company switcher' is on) will land in the SO. "
            "Out-of-company SKUs raise a warning and are skipped — they "
            "do not silently create a misrouted SO."
        ),
    )
    restrict_to_active_companies = fields.Boolean(
        string="Allow any active company",
        default=False,
        help=(
            "Off (default): a product must have stock in the wizard's "
            "primary company. On: a product is acceptable if it has "
            "stock in ANY company currently ticked in the user's "
            "company switcher (`self.env.companies`)."
        ),
    )
    route_by_shop_mapping = fields.Boolean(
        string="Route SO by shop mapping",
        default=True,
        help=(
            "When enabled, the company that each imported order lands "
            "in is decided by the wms.shop.company.map table — looked "
            "up by the shop name in the file. Falls back to the "
            "wizard's selected company when no mapping exists. Disable "
            "to force every SO into the wizard's primary company."
        ),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kob_allowed_companies(self):
        if self.restrict_to_active_companies:
            return self.env.companies or self.company_id
        return self.company_id

    def _kob_product_has_stock(self, product, allowed_companies):
        """True if `product` has > 0 on-hand qty in an internal location
        of any company in `allowed_companies`."""
        if not product or not allowed_companies:
            return False
        Quant = self.env["stock.quant"].sudo()
        return bool(Quant.search_count([
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "in", allowed_companies.ids),
            ("quantity", ">", 0),
        ]))

    def _kob_product_home_company(self, product, allowed_companies):
        """Return res.company holding the most stock for `product`
        among `allowed_companies`. Used by callers that want to route,
        not just validate."""
        Quant = self.env["stock.quant"].sudo()
        per_company = {}
        for q in Quant.search([
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "in", allowed_companies.ids),
            ("quantity", ">", 0),
        ]):
            per_company[q.company_id.id] = (
                per_company.get(q.company_id.id, 0) + q.quantity
            )
        if not per_company:
            return self.env["res.company"].browse()
        if self.company_id and self.company_id.id in per_company:
            return self.company_id
        best = max(per_company, key=lambda cid: per_company[cid])
        return self.env["res.company"].browse(best)

    # ------------------------------------------------------------------
    # Override product resolver — silently fail when out-of-company
    # ------------------------------------------------------------------

    def _resolve_product(self, sku, brand=None):
        product = super()._resolve_product(sku, brand)
        if not self.enforce_product_company or not product:
            return product

        allowed = self._kob_allowed_companies()
        if self._kob_product_has_stock(product, allowed):
            return product

        # Product exists globally but has no stock in any allowed company.
        # Find where it DOES live so the log can tell the user clearly.
        all_companies = self.env["res.company"].sudo().search([])
        elsewhere = self._kob_product_home_company(product, all_companies)
        if elsewhere:
            _logger.warning(
                "Marketplace import: SKU %s exists in %s but not in any "
                "allowed company %s — skipping line.",
                sku, elsewhere.name, allowed.mapped("name"),
            )
        else:
            _logger.warning(
                "Marketplace import: SKU %s exists but has no on-hand "
                "stock anywhere — skipping line.", sku,
            )
        # Returning False makes the parent log "WARN — SKU not found"
        # and skip the line; that's the "ขึ้นฟ้อง" the user asked for.
        # We also append a more specific note to import_log so the user
        # sees exactly which company actually owns the product.
        if elsewhere:
            extra = _(
                "⚠ SKU %(sku)s exists in %(co)s but is out of stock in "
                "allowed companies (%(allowed)s). Line skipped."
            ) % {
                "sku": sku,
                "co": elsewhere.name,
                "allowed": ", ".join(allowed.mapped("name")) or "(none)",
            }
        else:
            extra = _(
                "⚠ SKU %(sku)s has no on-hand stock in any company. "
                "Line skipped — assign stock first."
            ) % {"sku": sku}
        self.log = (self.log or "") + extra + "\n"
        return self.env["product.product"]

    # ------------------------------------------------------------------
    # Shop-name → Company routing (Phase 2)
    # ------------------------------------------------------------------

    def action_import(self):
        """Dispatch to the shop-routed flow when the new flag is on,
        otherwise fall through to the parent (which uses self.company_id
        for every SO)."""
        self.ensure_one()
        if not self.route_by_shop_mapping:
            return super().action_import()
        return self._kob_action_import_with_routing()

    def _kob_action_import_with_routing(self):
        """Reproduces the parent's import loop but resolves the target
        company per order via wms.shop.company.map. SOs are split when
        a single file contains orders from shops mapped to different
        companies."""
        if not self.file_data and not self.attachment_ids:
            raise UserError(_(
                "Please upload at least one Excel/CSV file."
            ))

        ShopMap = self.env["wms.shop.company.map"].sudo()
        Company = self.env["res.company"].sudo()
        SaleOrder = self.env["sale.order"].sudo()

        allowed = self._kob_allowed_companies() if self.enforce_product_company \
            else self.env["res.company"].sudo().search([])
        if not allowed:
            allowed = self.company_id

        # 1. Parse files (parent helpers)
        records = []
        per_file_log = []
        for filename, raw, platform in self._collect_files():
            try:
                file_records = self._parse_blob(raw, filename)
            except UserError as e:
                per_file_log.append(f"FAIL {filename} — {e.args[0]}")
                continue
            for r in file_records:
                r["__platform"] = platform
                r["__source_file"] = filename
            per_file_log.append(
                f"READ {filename} — {len(file_records)} rows ({platform})"
            )
            records.extend(file_records)

        if not records:
            raise UserError(_(
                "No order rows could be parsed.\n\n%s"
            ) % "\n".join(per_file_log))

        by_order = defaultdict(list)
        for r in records:
            by_order[(r["__platform"], r["order_sn"])].append(r)

        log_lines = list(per_file_log)
        sales = self.env["sale.order"]
        fake_tag = self.env.ref(
            "kob_marketplace_import.tag_fake_order",
            raise_if_not_found=False,
        )

        partner_cache = {}
        source_cache = {}

        def _partner_for(platform):
            if platform in partner_cache:
                return partner_cache[platform]
            name = _PARTNER_BY_PLATFORM.get(platform, "Unknown")
            partner = self.env["res.partner"].search(
                [("name", "=", name)], limit=1,
            )
            if not partner:
                partner = self.env["res.partner"].create({
                    "name": name, "is_company": True, "customer_rank": 1,
                })
            partner_cache[platform] = partner
            return partner

        def _source_for(platform, shop_name):
            full = f"{_PRETTY.get(platform, platform.title())}_{shop_name}"
            if full in source_cache:
                return source_cache[full]
            s = self.env["utm.source"].search(
                [("name", "=", full)], limit=1,
            )
            if not s:
                s = self.env["utm.source"].create({"name": full})
            source_cache[full] = s
            return s

        for (platform, order_sn), lines in by_order.items():
            head = lines[0]
            shop = head.get("shop") or "Unknown"
            source = _source_for(platform, shop)
            source_name = source.name  # e.g. "Shopee_DaengGiMeoRi"

            # Resolve target company via shop mapping
            target_company = ShopMap.resolve(source_name, allowed_companies=allowed)
            if not target_company:
                # Fall back: wizard's primary company
                target_company = self.company_id
                log_lines.append(
                    f"⚠ {order_sn} — shop '{source_name}' not in "
                    f"wms.shop.company.map; falling back to {target_company.name}. "
                    f"Map this shop to silence the warning."
                )

            if target_company not in allowed:
                log_lines.append(
                    f"SKIP {order_sn} — shop '{source_name}' maps to "
                    f"{target_company.name} which is not in the allowed "
                    f"companies ({', '.join(allowed.mapped('name'))})."
                )
                continue

            # De-duplicate by client_order_ref scoped to the resolved company
            existing = SaleOrder.with_company(target_company).search([
                ("client_order_ref", "=", order_sn),
                ("company_id", "=", target_company.id),
            ], limit=1)
            if existing:
                log_lines.append(
                    f"SKIP {order_sn} — already imported into "
                    f"{target_company.name} ({existing.name})"
                )
                continue

            partner = _partner_for(platform)
            tag_ids = [(4, fake_tag.id)] if (fake_tag and any(
                l.get("fake") for l in lines
            )) else []

            # Resolve target warehouse for the routed company
            target_wh = self.env["stock.warehouse"].sudo().search([
                ("company_id", "=", target_company.id),
            ], limit=1)
            if (self.fbs_auto_route and platform == "shopee"
                    and order_sn.upper().endswith("-FBS")):
                shopee_wh = self.env["stock.warehouse"].sudo().search([
                    ("company_id", "=", target_company.id),
                    ("name", "ilike", "SHOPEE"),
                ], limit=1)
                if shopee_wh:
                    target_wh = shopee_wh
            if not target_wh:
                log_lines.append(
                    f"SKIP {order_sn} — {target_company.name} has no "
                    f"stock.warehouse configured."
                )
                continue

            order_lines_vals = []
            for ln in lines:
                # _resolve_product (Phase 1 override) already enforces
                # product-in-allowed-company when enforce_product_company
                # is on. We additionally bind it to the *routed* company
                # by temporarily switching env company.
                product = self.with_company(target_company)._resolve_product(
                    ln["sku"], ln.get("brand"),
                )
                if not product:
                    log_lines.append(
                        f"WARN {order_sn} — SKU '{ln['sku']}' not "
                        f"resolvable in {target_company.name}, line skipped"
                    )
                    continue
                if self.auto_adjust_lot:
                    self.with_company(target_company)._ensure_stock_with_lot(
                        product, float(ln.get("qty") or 0), target_wh,
                        unit_cost=float(ln.get("price") or 0),
                        order_sn=order_sn,
                    )
                vals = {
                    "product_id": product.id,
                    "product_uom_qty": ln["qty"],
                }
                if ln.get("price"):
                    vals["price_unit"] = ln["price"]
                order_lines_vals.append((0, 0, vals))

            if not order_lines_vals:
                log_lines.append(
                    f"SKIP {order_sn} — all lines unresolved (target {target_company.name})"
                )
                continue

            so_name = str(order_sn).strip() or False
            so_vals = {
                "name":             so_name,
                "partner_id":       partner.id,
                "client_order_ref": order_sn,
                "company_id":       target_company.id,
                "warehouse_id":     target_wh.id,
                "date_order":       self._normalize_date(head["order_date"]),
                "source_id":        source.id,
                "tag_ids":          tag_ids,
                "order_line":       order_lines_vals,
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
                so = SaleOrder.with_company(target_company).create(so_vals)
            except Exception as e:
                log_lines.append(
                    f"❌ {order_sn} → {target_company.name}: SO failed — {e}"
                )
                _logger.exception("SO create failed for %s", order_sn)
                continue
            sales |= so
            tag = "↪ routed" if target_company != self.company_id else "OK   "
            log_lines.append(
                f"{tag} {order_sn} → {target_company.name} → {so.name} "
                f"({len(so.order_line)} lines)"
            )

            if self.auto_confirm:
                so.action_confirm()
                if self.auto_assign:
                    for picking in so.picking_ids:
                        picking.action_assign()
                        picking.write({
                            "x_kob_source_ref":     source.id,
                            "x_kob_order_date_ref": so.date_order,
                            "x_kob_fake_order":     bool(tag_ids),
                        })
                        for move in picking.move_ids:
                            brand = (move.sale_line_id and
                                     move.sale_line_id.x_kob_brand) \
                                or move.product_id.x_kob_brand
                            if brand:
                                move.write({"x_kob_brand": brand})
                        if hasattr(picking, "action_create_wms_order"):
                            try:
                                picking.action_create_wms_order()
                            except Exception as e:
                                _logger.warning(
                                    "WMS bridge failed for %s: %s",
                                    picking.name, e,
                                )

        self.write({
            "state":          "done",
            "log":            "\n".join(log_lines),
            "sale_order_ids": [(6, 0, sales.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": _("Marketplace Import — Result"),
        }
