# -*- coding: utf-8 -*-
"""Marketplace order import wizard.

Reads an Excel/CSV with one row per (order_sn, sku, qty) and creates
sale.order + lines + stock.picking with the x_kob_* fields the
Print_Label-App pipeline expects.

Excel layout (any of the column-name variants are accepted, case-insensitive):
    order_sn      | order # | order number
    shop          | shop_name
    order_date    | order_at | date
    sku           | sku_code
    qty           | quantity
    brand         | x_kob_brand
    fake          | fake_order   (Y / N / True / False / 1 / 0)
    [optional] price
"""
from __future__ import annotations

import base64
import csv
import io
import logging
from datetime import datetime, timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Map of platform → expected res.partner.name (must match Print_Label-App).
_PARTNER_BY_PLATFORM = {
    "shopee": "ECOMMERCE : SHOPEE",
    "tiktok": "ECOMMERCE : TIKTOK",
    "lazada": "ECOMMERCE : LAZADA",
}
_PRETTY = {"shopee": "Shopee", "tiktok": "TikTok", "lazada": "Lazada"}

# Aliases we accept for each logical column.  English-only — Shopee /
# Lazada / TikTok official exports all use English headers (``Order
# ID``, ``SKU``, ``Order Date``, ``Quantity``, ``Unit Price``,
# ``Net Sale``, ``Shipping Fee``, …).  Thai column names are
# intentionally NOT accepted (per user policy: keep imports machine-
# readable).  Compared case-insensitively after _normalize() collapses
# punctuation + whitespace.
_COL_ALIASES = {
    "order_sn": (
        "order_sn", "order_no", "order_number", "order_id", "orderid",
        "order#", "order", "ordernumber", "order_ref", "ordersn",
        "platform_order_id", "marketplace_order_id",
    ),
    "shop": (
        "shop", "shop_name", "shopname", "store", "store_name",
    ),
    "order_date": (
        "order_date", "date", "order_at", "date_order", "ordered_at",
        "orderdate", "ordereddate",
    ),
    "sku": (
        "sku", "sku_code", "code", "product_code", "item_id", "itemid",
        "product_sku", "default_code", "skucode",
    ),
    "qty": (
        "qty", "quantity", "product_uom_qty", "count", "num",
    ),
    "brand": (
        "brand", "x_kob_brand", "brand_name", "brandname",
    ),
    "fake": (
        "fake", "fake_order", "x_kob_fake_order", "is_fake", "test",
    ),
    "price": (
        "price", "unit_price", "price_unit", "selling_price",
        "unitprice", "sellingprice", "net_sale", "netsale",
    ),
}


def _normalize(s):
    """Lower-case, strip leading/trailing space, and squeeze inner
    whitespace + common punctuation away so that ``Order #``,
    ``order_number``, ``Order ID`` and ``ORDER NUMBER`` all collapse
    to the same canonical form for alias matching.  Non-ASCII
    characters (incl. Thai) are dropped entirely so they cannot
    accidentally match."""
    if s is None:
        return ""
    out = str(s).strip().lower()
    keep = []
    for ch in out:
        # Keep ASCII alnum + underscore.  Drop everything else.
        if (ch.isascii() and ch.isalnum()) or ch == "_":
            keep.append(ch)
    return "".join(keep)


# Pre-normalise the alias table once at import-time so column matching
# can compare apples to apples.
_COL_ALIASES_NORM = {
    logical: tuple(_normalize(a) for a in aliases)
    for logical, aliases in _COL_ALIASES.items()
}


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return False
    s = str(v).strip().lower()
    return s in ("y", "yes", "true", "1", "t")


class MarketplaceImportWizard(models.TransientModel):
    _name = "kob.marketplace.import.wizard"
    _description = "Import Marketplace Orders"

    platform = fields.Selection(
        [("shopee", "Shopee"), ("tiktok", "TikTok"), ("lazada", "Lazada")],
        required=True, default="shopee",
    )
    company_id = fields.Many2one(
        "res.company", required=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse", required=True,
        domain="[('company_id', '=', company_id)]",
        compute="_compute_default_warehouse",
        store=True, readonly=False,
    )

    @api.depends("company_id", "platform")
    def _compute_default_warehouse(self):
        # Convention: marketplace orders default to the company's
        # "Online" warehouse — name contains "Online" — fallback to
        # the first warehouse of that company.
        for w in self:
            if not w.company_id:
                w.warehouse_id = False
                continue
            online = self.env["stock.warehouse"].search([
                ("company_id", "=", w.company_id.id),
                ("name", "ilike", "Online"),
            ], limit=1)
            if not online:
                online = self.env["stock.warehouse"].search([
                    ("company_id", "=", w.company_id.id),
                ], limit=1)
            w.warehouse_id = online.id if online else False
    file_data = fields.Binary("Excel/CSV File")
    filename = fields.Char()
    # Multi-file mode — drag-and-drop the whole folder at once.  Each
    # ir.attachment is one xlsx/csv file.  Platform is auto-detected
    # from the filename's first underscore-separated token (Shopee /
    # Lazada / TikTok).
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Excel/CSV Files (batch)",
        help="Drop the whole folder here — each file is processed in "
             "turn.  Platform is auto-detected from the filename "
             "(Shopee_… / Lazada_… / Tiktok_…).",
    )
    auto_confirm = fields.Boolean("Confirm SOs", default=True)
    auto_assign = fields.Boolean("Reserve stock (assign)", default=True)
    auto_create_product = fields.Boolean(
        "Auto-create missing products",
        default=True,
        help="If a SKU in the file is not in product.product, create a "
             "lot-tracked storable product on the fly with default_code "
             "= SKU and x_kob_brand auto-derived from the filename.",
    )
    auto_adjust_lot = fields.Boolean(
        "Adjust stock (create lot + qty)",
        default=True,
        help="After auto-creating a product (or for any imported line "
             "where on-hand qty is insufficient), generate a stock.lot "
             "and post an inventory adjustment so the Sale Order can be "
             "reserved at confirmation time.  Lot name = "
             "AUTO-<YYYYMMDD>-<SKU>.",
    )
    fbs_auto_route = fields.Boolean(
        "FBS auto-route", default=True,
        help="If the order_sn ends with -FBS (Shopee Fulfilled-By-Shopee), "
             "route to the company's *-SHOPEE warehouse instead of *-Online.",
    )

    # Results
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done")], default="draft",
    )
    log = fields.Text(readonly=True)
    sale_order_ids = fields.Many2many("sale.order", readonly=True)

    # ── Parsing ────────────────────────────────────────────────────
    @staticmethod
    def _detect_platform(filename):
        """Return one of 'shopee'|'lazada'|'tiktok' based on the
        filename's first token, or None if undetectable."""
        if not filename:
            return None
        stem = filename.rsplit(".", 1)[0]
        first = stem.split(" ", 1)[0].split("_", 1)[0].lower()
        if first.startswith("shopee"):
            return "shopee"
        if first.startswith("lazada"):
            return "lazada"
        if first.startswith("tiktok") or first.startswith("tikt"):
            return "tiktok"
        return None

    @staticmethod
    def _derive_brand_shop(filename):
        """Pull brand/shop from filename pattern
        ``<Platform>_<Brand>[_<Word>...] <Date> <Shift>...``."""
        if not filename:
            return (None, None)
        stem = filename.rsplit(".", 1)[0]
        head = stem.split(" ", 1)[0]
        parts = head.split("_")
        if len(parts) >= 2:
            shop = "_".join(parts[1:])
            return (shop, shop)
        return (None, None)

    def _parse_blob(self, raw, filename):
        """Parse one (raw bytes, filename) pair into a list of
        record dicts.  Replaces the previous instance-bound
        ``_parse_file`` so we can iterate over multiple files in a
        single import run."""
        name = (filename or "").lower()
        derived_brand, derived_shop = self._derive_brand_shop(filename)

        if name.endswith(".csv"):
            text = raw.decode("utf-8-sig")
            rdr = csv.reader(io.StringIO(text))
            rows = list(rdr)
            if not rows:
                raise UserError(_("File is empty."))
            header = [_normalize(c) for c in rows[0]]
            data = rows[1:]
        else:
            try:
                from openpyxl import load_workbook
            except ImportError:
                raise UserError(_(
                    "openpyxl is not installed in the Odoo container — "
                    "use a CSV file instead.",
                ))
            wb = load_workbook(io.BytesIO(raw), data_only=True)
            ws = wb.active
            iter_ = ws.iter_rows(values_only=True)
            header_row = next(iter_, None)
            if not header_row:
                raise UserError(_("File is empty."))
            header = [_normalize(c) for c in header_row]
            data = [r for r in iter_ if any(c is not None for c in r)]

        # Resolve column indexes (case + punctuation insensitive).
        col = {}
        for logical, aliases in _COL_ALIASES_NORM.items():
            for i, h in enumerate(header):
                if h in aliases:
                    col[logical] = i
                    break

        for required in ("order_sn", "sku", "qty"):
            if required not in col:
                # Show both the accepted aliases and the columns we
                # actually saw — much easier to fix the file.
                raise UserError(_(
                    "Required column missing: %(name)s.\n\n"
                    "Accepted aliases (case-insensitive): %(aliases)s\n\n"
                    "Columns found in your file: %(found)s\n\n"
                    "Fix: rename one of your columns to any accepted "
                    "alias, or add a new alias to _COL_ALIASES in "
                    "kob_marketplace_import/wizards/"
                    "marketplace_import_wizard.py.",
                ) % {
                    "name": required,
                    "aliases": ", ".join(_COL_ALIASES[required]),
                    "found": ", ".join(repr(h) for h in header) or "(empty)",
                })

        records = []
        for r in data:
            order_sn = r[col["order_sn"]]
            if not order_sn:
                continue
            records.append({
                "order_sn": str(order_sn).strip(),
                "shop": (
                    str(r[col["shop"]]).strip()
                    if "shop" in col and r[col["shop"]]
                    else derived_shop
                ),
                "order_date": (
                    r[col["order_date"]]
                    if "order_date" in col else None
                ),
                "sku": str(r[col["sku"]]).strip(),
                "qty": float(r[col["qty"]] or 0),
                "brand": (
                    str(r[col["brand"]]).strip()
                    if "brand" in col and r[col["brand"]]
                    else derived_brand
                ),
                "fake": _to_bool(r[col["fake"]]) if "fake" in col else False,
                "price": float(r[col["price"]] or 0)
                          if "price" in col else 0.0,
            })
        return records

    # ── Helpers ───────────────────────────────────────────────────
    def _get_partner(self):
        partner = self.env["res.partner"].search(
            [("name", "=", _PARTNER_BY_PLATFORM[self.platform])], limit=1,
        )
        if not partner:
            partner = self.env["res.partner"].create({
                "name": _PARTNER_BY_PLATFORM[self.platform],
                "is_company": True, "customer_rank": 1,
            })
        return partner

    def _get_source(self, shop_name):
        full = f"{_PRETTY[self.platform]}_{shop_name}"
        s = self.env["utm.source"].search([("name", "=", full)], limit=1)
        if not s:
            s = self.env["utm.source"].create({"name": full})
        return s

    def _resolve_product(self, sku, brand=None):
        """Find the product.product matching ``sku`` (default_code OR
        x_kob_sku_code OR ``[SKU]`` prefix in name).  If ``self.
        auto_create_product`` is set and nothing matches, create a
        new product on the fly so the import can proceed."""
        prod = self.env["product.product"].search(
            [("default_code", "=", sku)], limit=1,
        )
        if not prod:
            prod = self.env["product.product"].search(
                [("x_kob_sku_code", "=", sku)], limit=1,
            )
        if not prod:
            # Match by [SKU] prefix in name
            prod = self.env["product.product"].search(
                [("name", "=ilike", f"[{sku}]%")], limit=1,
            )
        if prod:
            return prod
        if not self.auto_create_product:
            return prod
        # Auto-create — storable + lot-tracked so the WMS pipeline can
        # reserve / pick / pack.  Stock is seeded later via the
        # `_adjust_lot` helper triggered for each order line.
        name = sku
        if brand:
            name = "[%s] %s — auto-imported" % (sku, brand)
        else:
            name = "[%s] auto-imported" % sku
        new_prod = self.env["product.product"].sudo().create({
            "name":           name,
            "default_code":   sku,
            "x_kob_sku_code": sku,
            "x_kob_brand":    brand or "",
            "type":           "product",   # storable
            "tracking":       "lot",
            "sale_ok":        True,
            "purchase_ok":    False,
        })
        _logger.info(
            "Auto-created lot-tracked product %s (%s) for marketplace import",
            new_prod.id, sku,
        )
        return new_prod

    def _ensure_stock_with_lot(self, product, qty, warehouse, unit_cost=0.0):
        """Create a stock.lot for ``product`` (if needed) and post an
        inventory adjustment so ``qty`` is available in
        ``warehouse``'s stock location.  Returns the lot.

        ``unit_cost`` is stored on stock.lot.x_kob_cost_per_unit so
        per-lot valuation reports get the right basis.

        Idempotent: if a lot named AUTO-<YYYYMMDD>-<SKU> already
        exists with enough quantity, just top it up.
        """
        from datetime import date as _date

        if not product or qty <= 0 or not warehouse:
            return self.env["stock.lot"]

        loc = warehouse.lot_stock_id
        if not loc:
            return self.env["stock.lot"]

        sku = product.default_code or str(product.id)
        lot_name = "AUTO-%s-%s" % (_date.today().strftime("%Y%m%d"), sku)
        Lot = self.env["stock.lot"].sudo()
        lot = Lot.search([
            ("name", "=", lot_name),
            ("product_id", "=", product.id),
        ], limit=1)
        if not lot:
            lot = Lot.create({
                "name":               lot_name,
                "product_id":         product.id,
                "company_id":         warehouse.company_id.id,
                "x_kob_cost_per_unit": (
                    unit_cost or float(product.standard_price or 0)
                ),
            })
        elif unit_cost and not lot.x_kob_cost_per_unit:
            # First time we're seeing a meaningful cost — record it.
            lot.x_kob_cost_per_unit = unit_cost

        # Read the current on-hand for this lot at the warehouse stock
        # location.  Top up to (current + qty) via stock.quant
        # `inventory_quantity` field — this is Odoo's idiomatic
        # inventory-adjustment write path.
        Quant = self.env["stock.quant"].sudo()
        quant = Quant.search([
            ("product_id",  "=", product.id),
            ("location_id", "=", loc.id),
            ("lot_id",      "=", lot.id),
        ], limit=1)
        if quant:
            new_qty = (quant.quantity or 0) + qty
            quant.with_context(inventory_mode=True).write({
                "inventory_quantity": new_qty,
            })
            quant.action_apply_inventory()
        else:
            quant = Quant.with_context(inventory_mode=True).create({
                "product_id":         product.id,
                "location_id":        loc.id,
                "lot_id":             lot.id,
                "inventory_quantity": qty,
            })
            quant.action_apply_inventory()
        return lot

    def _normalize_date(self, value):
        if not value:
            return fields.Datetime.now()
        if isinstance(value, datetime):
            return fields.Datetime.to_string(
                value.replace(tzinfo=None) if value.tzinfo else value
            )
        s = str(value).strip().replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S",
                    "%d-%m-%Y"):
            try:
                return fields.Datetime.to_string(datetime.strptime(s, fmt))
            except ValueError:
                continue
        return fields.Datetime.now()

    # ── Main ──────────────────────────────────────────────────────
    def _collect_files(self):
        """Yield (filename, raw bytes, platform) tuples for every input
        file — single Excel/CSV via ``file_data`` AND the multi-file
        batch via ``attachment_ids``.  Platform is auto-detected from
        the filename; if it can't be detected we fall back to whatever
        is selected on the wizard."""
        if self.file_data:
            yield (
                self.filename or "upload.xlsx",
                base64.b64decode(self.file_data),
                self._detect_platform(self.filename) or self.platform,
            )
        for att in self.attachment_ids:
            raw = att.raw if att.raw else (
                base64.b64decode(att.datas) if att.datas else b""
            )
            if not raw:
                continue
            yield (
                att.name or "attachment.xlsx",
                raw,
                self._detect_platform(att.name) or self.platform,
            )

    def action_import(self):
        self.ensure_one()
        if not self.file_data and not self.attachment_ids:
            raise UserError(_(
                "Please upload at least one Excel/CSV file (single or "
                "drop the whole folder into 'Excel/CSV Files (batch)')."
            ))

        # Parse every input file.  Each row remembers its platform so
        # we use the right partner / source / warehouse.
        records = []
        per_file_log = []
        for filename, raw, platform in self._collect_files():
            try:
                file_records = self._parse_blob(raw, filename)
            except UserError as e:
                per_file_log.append("FAIL %s — %s" % (filename, e.args[0]))
                continue
            for r in file_records:
                r["__platform"] = platform
                r["__source_file"] = filename
            per_file_log.append(
                "READ %s — %d rows (%s)"
                % (filename, len(file_records), platform),
            )
            records.extend(file_records)

        if not records:
            raise UserError(_(
                "No order rows could be parsed.\n\n%s"
            ) % "\n".join(per_file_log))

        # Group rows by (platform, order_sn) — a single order_sn could
        # legally appear under different platforms.
        by_order = {}
        for r in records:
            key = (r["__platform"], r["order_sn"])
            by_order.setdefault(key, []).append(r)

        fake_tag = self.env.ref("kob_marketplace_import.tag_fake_order")
        SaleOrder = self.env["sale.order"].with_company(self.company_id)
        log_lines = list(per_file_log)
        sales = self.env["sale.order"]

        # Cache partner per platform to avoid repeated searches.
        partner_cache = {}

        def _partner_for(platform):
            if platform in partner_cache:
                return partner_cache[platform]
            name = _PARTNER_BY_PLATFORM[platform]
            partner = self.env["res.partner"].search([("name", "=", name)],
                                                     limit=1)
            if not partner:
                partner = self.env["res.partner"].create({
                    "name": name, "is_company": True, "customer_rank": 1,
                })
            partner_cache[platform] = partner
            return partner

        def _source_for(platform, shop_name):
            full = "%s_%s" % (_PRETTY[platform], shop_name)
            s = self.env["utm.source"].search([("name", "=", full)], limit=1)
            if not s:
                s = self.env["utm.source"].create({"name": full})
            return s

        for (platform, order_sn), lines in by_order.items():
            existing = SaleOrder.search([("client_order_ref", "=", order_sn)],
                                        limit=1)
            if existing:
                log_lines.append(f"SKIP {order_sn} — already imported "
                                 f"({existing.name})")
                continue

            partner = _partner_for(platform)
            head = lines[0]
            shop = head["shop"] or "Unknown"
            source = _source_for(platform, shop)
            tag_ids = [(4, fake_tag.id)] if any(l["fake"] for l in lines) \
                      else []

            order_lines_vals = []
            for ln in lines:
                product = self._resolve_product(ln["sku"], ln.get("brand"))
                if not product:
                    log_lines.append(
                        f"WARN {order_sn} — SKU '{ln['sku']}' not found, "
                        f"line skipped (toggle 'Auto-create missing "
                        f"products' to import it anyway)",
                    )
                    continue
                # Adj. Lot — make sure stock + a lot exists so the SO
                # can reserve at confirmation.  Cost basis = the price
                # captured from the Excel row, fallback to standard_price.
                if self.auto_adjust_lot:
                    self._ensure_stock_with_lot(
                        product,
                        float(ln.get("qty") or 0),
                        self.warehouse_id,
                        unit_cost=float(ln.get("price") or 0),
                    )
                vals = {
                    "product_id": product.id,
                    "product_uom_qty": ln["qty"],
                }
                if ln.get("price"):
                    vals["price_unit"] = ln["price"]
                order_lines_vals.append((0, 0, vals))

            if not order_lines_vals:
                log_lines.append(f"SKIP {order_sn} — all lines unresolved")
                continue

            # FBS auto-routing: if order_sn ends with "-FBS", route to the
            # company's *-SHOPEE warehouse (Shopee Fulfilled-By-Shopee).
            target_wh = self.warehouse_id
            if (self.fbs_auto_route
                and platform == "shopee"
                and order_sn.upper().endswith("-FBS")):
                shopee_wh = self.env["stock.warehouse"].search([
                    ("company_id", "=", self.company_id.id),
                    ("name", "ilike", "SHOPEE"),
                ], limit=1)
                if shopee_wh:
                    target_wh = shopee_wh

            so = SaleOrder.create({
                "partner_id":       partner.id,
                "client_order_ref": order_sn,
                "company_id":       self.company_id.id,
                "warehouse_id":     target_wh.id,
                "date_order":       self._normalize_date(head["order_date"]),
                "source_id":        source.id,
                "tag_ids":          tag_ids,
                "order_line":       order_lines_vals,
            })
            sales |= so
            log_lines.append(f"OK   {order_sn} → {so.name} ({len(so.order_line)} lines)")

            if self.auto_confirm:
                so.action_confirm()
                if self.auto_assign:
                    for picking in so.picking_ids:
                        picking.action_assign()
                        # Stamp x_kob_* fields onto the picking.
                        picking.write({
                            "x_kob_source_ref":     source.id,
                            "x_kob_order_date_ref": so.date_order,
                            "x_kob_fake_order":     bool(tag_ids),
                        })
                        # Propagate brand product → move.
                        for move in picking.move_ids:
                            brand = (move.sale_line_id and
                                     move.sale_line_id.x_kob_brand) \
                                    or move.product_id.x_kob_brand
                            if brand:
                                move.write({"x_kob_brand": brand})
                        # Bridge: create the wms.sales.order record so the
                        # KOB WMS Orders list / Pick / Pack screens see it.
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

    def action_open_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.sale_order_ids.ids)],
        }
