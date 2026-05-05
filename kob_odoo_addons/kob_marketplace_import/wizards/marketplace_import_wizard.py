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
        [("draft", "Draft"), ("running", "Running"), ("done", "Done")],
        default="draft",
    )
    log = fields.Text(readonly=True)
    sale_order_ids = fields.Many2many("sale.order", readonly=True)
    duplicate_order_ids = fields.Many2many(
        "sale.order", "kob_mp_import_dup_rel", "wiz_id", "so_id",
        readonly=True, string="Duplicate Sale Orders",
        help="Existing SOs that matched an imported order_sn — skipped.",
    )
    progress_total = fields.Integer(readonly=True, default=0)
    progress_done = fields.Integer(readonly=True, default=0)
    progress_pct = fields.Integer(readonly=True, default=0,
                                   help="Percent of orders processed.")
    imported_count = fields.Integer(readonly=True, default=0,
                                     string="Imported")
    duplicate_count = fields.Integer(readonly=True, default=0,
                                      string="Duplicates Skipped")
    unresolved_count = fields.Integer(readonly=True, default=0,
                                       string="Unresolved Skipped")
    duplicate_summary = fields.Text(readonly=True,
                                     string="Duplicate Details",
                                     help="One line per skipped duplicate "
                                          "with the existing SO it matched.")

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
        # ``_ensure_stock_with_lot`` helper triggered for each order
        # line.
        #
        # Odoo's display_name already prepends ``[default_code]`` so
        # we leave the ``name`` field free of the SKU prefix — that's
        # what was producing the duplicated ``[SWB700] [SWB700]`` you'd
        # see in SO line displays.
        if brand:
            name = "%s — auto-imported" % brand
        else:
            name = "auto-imported"
        # Odoo 19 split product.template.type — 'product' is no longer
        # accepted.  We use type='consu' + is_storable=True for the
        # stockable + lot-tracked variant.
        new_prod_vals = {
            "name":           name,
            "default_code":   sku,
            "barcode":        sku,
            "x_kob_sku_code": sku,
            "x_kob_brand":    brand or "",
            "type":           "consu",
            "tracking":       "lot",
            "sale_ok":        True,
            "purchase_ok":    False,
        }
        if "is_storable" in self.env["product.template"]._fields:
            new_prod_vals["is_storable"] = True
        # ``barcode`` is unique on product.product; in the rare case
        # the same SKU got registered as a barcode by another import
        # path, fall back to no-barcode rather than crashing.
        try:
            new_prod = self.env["product.product"].sudo().create(new_prod_vals)
        except Exception as e:
            _logger.warning(
                "Barcode '%s' clashes with an existing product — "
                "creating without barcode (%s)", sku, e,
            )
            new_prod_vals.pop("barcode", None)
            new_prod = self.env["product.product"].sudo().create(new_prod_vals)
        _logger.info(
            "Auto-created lot-tracked product %s (%s) for marketplace import",
            new_prod.id, sku,
        )
        return new_prod

    def _ensure_stock_with_lot(self, product, qty, warehouse, unit_cost=0.0,
                               order_sn=None):
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
        # Lot name traceability: prefer the marketplace order # so each
        # imported order's stock has a clean audit trail back to the
        # platform's order_sn.  Fall back to AUTO-<date>-<sku> when no
        # order_sn is available (e.g. manual top-ups).
        if order_sn:
            lot_name = "%s-%s" % (str(order_sn).strip(), sku)
        else:
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

        # Top up the lot quantity at the warehouse stock location.
        #
        # We avoid ``action_apply_inventory()`` because the kob_wms
        # addon overrides ``_apply_inventory()`` with a no-arg
        # signature that crashes against Odoo 19's date-aware caller.
        # Instead, write ``quantity`` directly with the inventory_mode
        # context — the same path Odoo's own bulk-update wizards use
        # under the hood.
        Quant = self.env["stock.quant"].sudo().with_context(
            inventory_mode=True,
        )
        quant = Quant.search([
            ("product_id",  "=", product.id),
            ("location_id", "=", loc.id),
            ("lot_id",      "=", lot.id),
        ], limit=1)
        target_qty = float(quant.quantity or 0) + qty if quant else qty
        if quant:
            quant.write({"quantity": target_qty})
        else:
            quant = Quant.create({
                "product_id":  product.id,
                "location_id": loc.id,
                "lot_id":      lot.id,
                "quantity":    target_qty,
            })
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

    def _notify_progress(self, done, total, last_label):
        """Push a live toast to the current user's bus channel.

        Frontend (web client) listens on the user partner channel and
        shows a sticky toast — refreshed in-place each time we send.
        """
        try:
            pct = int(done * 100 / total) if total else 100
            msg = _("Marketplace Import: %(done)s / %(total)s "
                    "(%(pct)s%%) — %(last)s",
                    done=done, total=total, pct=pct, last=last_label)
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "title": _("Marketplace Import"),
                    "message": msg,
                    "sticky": done < total,
                    "type": "info",
                },
            )
        except Exception as e:
            _logger.debug("progress notify skipped: %s", e)

    def action_import(self):
        self.ensure_one()
        # ── Explicit company selection guard ────────────────────────
        # Without this, env.company silently routed every BTV file into
        # KOB. A required field on the model isn't enough — multi-company
        # users may still trigger the wizard with the wrong env.company.
        if not self.company_id:
            raise UserError(_(
                "⚠ ต้องเลือกบริษัทก่อน import\n\n"
                "Please tick a Company before importing. The marketplace "
                "import will create Sales Orders + Pickings under the "
                "selected company. Choosing the wrong company moves all "
                "stock movement and invoicing to the wrong books."
            ))
        if not self.warehouse_id:
            raise UserError(_(
                "⚠ ต้องเลือก Warehouse ของบริษัท %s ก่อน import"
            ) % self.company_id.name)
        if self.warehouse_id.company_id != self.company_id:
            raise UserError(_(
                "⚠ Warehouse %s อยู่ในบริษัท %s แต่คุณเลือกบริษัท %s — "
                "ไม่ตรงกัน เลือก warehouse ใหม่ให้ตรงกับบริษัท"
            ) % (
                self.warehouse_id.name,
                self.warehouse_id.company_id.name,
                self.company_id.name,
            ))
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
        # Beauty Vill product tag — products bearing it route to BTV-WH2 (Online).
        btv_tag = self.env.ref(
            "kob_marketplace_import.product_tag_beauty_vill",
            raise_if_not_found=False,
        )
        btv_wh = self.env["stock.warehouse"].search(
            [("code", "=", "B-On")], limit=1,
        ) if btv_tag else self.env["stock.warehouse"]
        SaleOrder = self.env["sale.order"].with_company(self.company_id)
        log_lines = list(per_file_log)
        sales = self.env["sale.order"]

        # ── Progress tracking ─────────────────────────────────────────
        total = len(by_order)
        self.write({
            "state": "running",
            "progress_total": total,
            "progress_done": 0,
            "progress_pct": 0,
            "imported_count": 0,
            "duplicate_count": 0,
            "unresolved_count": 0,
        })
        self.env.cr.commit()
        self._notify_progress(0, total, "Starting…")
        completed = 0
        imported_n = 0
        duplicate_n = 0
        unresolved_n = 0
        duplicate_so_ids = []
        duplicate_lines = []  # detailed log for duplicate_summary field

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
            # Robust duplicate check: match either client_order_ref OR
            # name (marketplace import sets SO.name = order_sn too).
            existing = SaleOrder.search([
                "|",
                ("client_order_ref", "=", order_sn),
                ("name", "=", order_sn),
            ], limit=1)
            if existing:
                duplicate_n += 1
                duplicate_so_ids.append(existing.id)
                detail = (
                    f"{order_sn}  →  existing SO {existing.name} "
                    f"(state={existing.state}, "
                    f"date={existing.date_order and existing.date_order.strftime('%Y-%m-%d') or '—'}, "
                    f"customer={existing.partner_id.name or '—'})"
                )
                duplicate_lines.append(detail)
                log_lines.append(f"SKIP {order_sn} — already imported "
                                 f"({existing.name})")
                # Still count toward progress so the bar reaches 100%.
                completed += 1
                pct = int(completed * 100 / total) if total else 100
                self.write({
                    "progress_done": completed,
                    "progress_pct": pct,
                    "duplicate_count": duplicate_n,
                })
                if completed % 5 == 0 or completed == total:
                    self.env.cr.commit()
                self._notify_progress(
                    completed, total,
                    f"Skipped duplicate {order_sn}",
                )
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
                # Lot name carries the marketplace order_sn for trace.
                if self.auto_adjust_lot:
                    self._ensure_stock_with_lot(
                        product,
                        float(ln.get("qty") or 0),
                        self.warehouse_id,
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
                unresolved_n += 1
                log_lines.append(f"SKIP {order_sn} — all lines unresolved")
                completed += 1
                pct = int(completed * 100 / total) if total else 100
                self.write({
                    "progress_done": completed,
                    "progress_pct": pct,
                    "unresolved_count": unresolved_n,
                })
                if completed % 5 == 0 or completed == total:
                    self.env.cr.commit()
                self._notify_progress(
                    completed, total,
                    f"Skipped (unresolved) {order_sn}",
                )
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

            # Beauty Vill tag → BTV-WH2 (Online) + BTV company. Wins over
            # warehouse_id but yields to FBS routing above. Swapping the
            # company keeps SO.company_id == warehouse.company_id so create
            # passes the cross-company validation.
            so_company_id = self.company_id.id
            if (btv_tag and btv_wh
                and not (platform == "shopee"
                         and order_sn.upper().endswith("-FBS"))):
                line_products = self.env["product.product"].browse(
                    [v[2]["product_id"] for v in order_lines_vals
                     if v and v[2] and v[2].get("product_id")]
                )
                if any(btv_tag.id in p.product_tag_ids.ids
                       or btv_tag.id in p.product_tmpl_id.product_tag_ids.ids
                       for p in line_products):
                    target_wh = btv_wh
                    so_company_id = btv_wh.company_id.id

            # Use the platform order number as the SO reference so the
            # operations team scans / searches the same identifier
            # everywhere (Excel, label, picking, accounting).  Odoo
            # accepts an explicit ``name`` value at create time and
            # skips the ir.sequence generation.  We still keep
            # ``client_order_ref`` populated for backwards-compatible
            # reporting.
            so_name = str(order_sn).strip() or False
            so_vals = {
                "name":             so_name,
                "partner_id":       partner.id,
                "client_order_ref": order_sn,
                "company_id":       so_company_id,
                "warehouse_id":     target_wh.id,
                "date_order":       self._normalize_date(head["order_date"]),
                "source_id":        source.id,
                "tag_ids":          tag_ids,
                "order_line":       order_lines_vals,
            }
            # Default Order Type = "Normal Order" so the picking
            # downstream shows it (mirrors UAT behaviour).
            normal_type = self.env.ref(
                "kob_marketplace_import.sale_order_type_normal",
                raise_if_not_found=False,
            )
            if normal_type:
                so_vals["sale_order_type_id"] = normal_type.id
            # Default Sales Team = eMarketplace (matches UAT).
            emarket_team = self.env["crm.team"].search(
                [("name", "=", "eMarketplace")], limit=1,
            )
            if emarket_team:
                so_vals["team_id"] = emarket_team.id
            # Re-bind company context if the order was BTV-routed.
            so_creator = (
                self.env["sale.order"].with_company(so_company_id)
                if so_company_id != self.company_id.id
                else SaleOrder
            )
            so = so_creator.create(so_vals)
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

            # ── Per-order progress: update + commit + notify ─────────
            completed += 1
            imported_n += 1
            pct = int(completed * 100 / total) if total else 100
            self.write({
                "progress_done": completed,
                "progress_pct": pct,
                "imported_count": imported_n,
            })
            # Commit every 5 orders (or last) so a refresh shows progress
            # and a crash doesn't lose imported orders. Notify on every
            # order so the user sees a live toast counter.
            if completed % 5 == 0 or completed == total:
                self.env.cr.commit()
            self._notify_progress(completed, total,
                                   f"Imported {order_sn}")

        # ── Final summary write ───────────────────────────────────────
        dup_summary = (
            "\n".join(duplicate_lines) if duplicate_lines
            else _("No duplicates in this batch — every order_sn was new.")
        )
        self.write({
            "state":            "done",
            "log":              "\n".join(log_lines),
            "sale_order_ids":   [(6, 0, sales.ids)],
            "duplicate_order_ids": [(6, 0, list(set(duplicate_so_ids)))],
            "duplicate_summary":   dup_summary,
            "progress_pct":     100,
            "imported_count":   imported_n,
            "duplicate_count":  duplicate_n,
            "unresolved_count": unresolved_n,
        })
        self.env.cr.commit()

        # Final summary toast — non-sticky, with breakdown.
        try:
            summary_msg = _(
                "Import complete: %(ok)s new, %(dup)s duplicates skipped, "
                "%(unres)s unresolved (total %(tot)s).",
                ok=imported_n, dup=duplicate_n, unres=unresolved_n, tot=total,
            )
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "title": _("Marketplace Import — Done"),
                    "message": summary_msg,
                    "sticky": True,
                    "type": "warning" if duplicate_n or unresolved_n else "success",
                },
            )
        except Exception as e:
            _logger.debug("final summary notify skipped: %s", e)
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

    def action_open_duplicates(self):
        """Open the SOs that were skipped because they already existed."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Skipped (Already Imported)"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.duplicate_order_ids.ids)],
        }
