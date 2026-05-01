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

# Aliases we accept for each logical column.
_COL_ALIASES = {
    "order_sn":  ("order_sn", "order #", "order number", "order_no",
                  "order_number"),
    "shop":      ("shop", "shop_name", "shopname"),
    "order_date":("order_date", "date", "order_at", "date_order"),
    "sku":       ("sku", "sku_code", "code"),
    "qty":       ("qty", "quantity", "product_uom_qty"),
    "brand":     ("brand", "x_kob_brand"),
    "fake":      ("fake", "fake_order", "x_kob_fake_order"),
    "price":     ("price", "unit_price", "price_unit"),
}


def _normalize(s):
    return (s or "").strip().lower().replace(" ", "_")


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
    file_data = fields.Binary("Excel/CSV File", required=True)
    filename = fields.Char()
    auto_confirm = fields.Boolean("Confirm SOs", default=True)
    auto_assign = fields.Boolean("Reserve stock (assign)", default=True)
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
    def _parse_file(self):
        if not self.file_data:
            raise UserError(_("Please upload an Excel or CSV file."))
        raw = base64.b64decode(self.file_data)
        name = (self.filename or "").lower()

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

        # Resolve column indexes.
        col = {}
        for logical, aliases in _COL_ALIASES.items():
            for i, h in enumerate(header):
                if h in aliases:
                    col[logical] = i
                    break

        for required in ("order_sn", "sku", "qty"):
            if required not in col:
                raise UserError(_(
                    "Required column missing: %s.  Accepted aliases: %s",
                ) % (required, ", ".join(_COL_ALIASES[required])))

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
                    else None
                ),
                "order_date": (
                    r[col["order_date"]]
                    if "order_date" in col else None
                ),
                "sku": str(r[col["sku"]]).strip(),
                "qty": float(r[col["qty"]] or 0),
                "brand": (
                    str(r[col["brand"]]).strip()
                    if "brand" in col and r[col["brand"]] else None
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

    def _resolve_product(self, sku):
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
        return prod

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
    def action_import(self):
        self.ensure_one()
        records = self._parse_file()
        if not records:
            raise UserError(_("No order rows found in the file."))

        # Group rows by order_sn.
        by_order = {}
        for r in records:
            by_order.setdefault(r["order_sn"], []).append(r)

        partner = self._get_partner()
        fake_tag = self.env.ref("kob_marketplace_import.tag_fake_order")
        SaleOrder = self.env["sale.order"].with_company(self.company_id)
        log_lines = []
        sales = self.env["sale.order"]

        for order_sn, lines in by_order.items():
            existing = SaleOrder.search([("client_order_ref", "=", order_sn)],
                                        limit=1)
            if existing:
                log_lines.append(f"SKIP {order_sn} — already imported "
                                 f"({existing.name})")
                continue

            head = lines[0]
            shop = head["shop"] or "Unknown"
            source = self._get_source(shop)
            tag_ids = [(4, fake_tag.id)] if any(l["fake"] for l in lines) \
                      else []

            order_lines_vals = []
            for ln in lines:
                product = self._resolve_product(ln["sku"])
                if not product:
                    log_lines.append(
                        f"WARN {order_sn} — SKU '{ln['sku']}' not found, "
                        f"line skipped",
                    )
                    continue
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
                and self.platform == "shopee"
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
