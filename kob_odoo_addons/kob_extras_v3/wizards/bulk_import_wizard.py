# -*- coding: utf-8 -*-
"""Phase 35 — Bulk CSV importer for products / partners / inventory.

Reads CSV file → upsert by external key.
"""
import base64
import csv
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobBulkImportWizard(models.TransientModel):
    _name = "kob.bulk.import.wizard"
    _description = "KOB Bulk CSV Import"

    target = fields.Selection(
        [
            ("product", "Products (default_code, name, list_price, barcode)"),
            ("partner", "Partners (name, email, phone, type)"),
            ("inventory", "Inventory Quants (default_code, location, qty, lot_name)"),
        ],
        required=True, default="product",
    )
    file_data = fields.Binary(string="CSV File", required=True)
    file_name = fields.Char()
    skip_header = fields.Boolean(default=True)
    delimiter = fields.Char(default=",")

    # Output
    rows_processed = fields.Integer(readonly=True)
    rows_created = fields.Integer(readonly=True)
    rows_updated = fields.Integer(readonly=True)
    rows_failed = fields.Integer(readonly=True)
    log = fields.Text(readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("No file uploaded"))
        raw = base64.b64decode(self.file_data).decode("utf-8-sig")
        reader = csv.reader(io.StringIO(raw), delimiter=self.delimiter)
        rows = list(reader)
        if self.skip_header and rows:
            rows = rows[1:]

        method_name = f"_import_{self.target}"
        method = getattr(self, method_name, None)
        if not method:
            raise UserError(_("No importer for %s") % self.target)
        created, updated, failed, log = method(rows)
        self.write({
            "rows_processed": len(rows),
            "rows_created": created,
            "rows_updated": updated,
            "rows_failed": failed,
            "log": log[:50000],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _import_product(self, rows):
        created, updated, failed = 0, 0, 0
        log_lines = []
        Product = self.env["product.template"]
        for row in rows:
            try:
                code, name, price, barcode = (row + ["", "", "0", ""])[:4]
                if not code:
                    continue
                existing = Product.search([("default_code", "=", code)], limit=1)
                vals = {
                    "default_code": code,
                    "name": name or code,
                    "list_price": float(price or 0),
                    "barcode": barcode or False,
                }
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Product.create(vals)
                    created += 1
            except Exception as e:
                failed += 1
                log_lines.append(f"Row {row}: {e}")
        return created, updated, failed, "\n".join(log_lines)

    def _import_partner(self, rows):
        created, updated, failed = 0, 0, 0
        log_lines = []
        Partner = self.env["res.partner"]
        for row in rows:
            try:
                name, email, phone, type_ = (row + ["", "", "", "contact"])[:4]
                if not name:
                    continue
                existing = Partner.search([
                    ("name", "=", name), ("email", "=", email or False),
                ], limit=1)
                vals = {
                    "name": name,
                    "email": email or False,
                    "phone": phone or False,
                    "type": type_ or "contact",
                }
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Partner.create(vals)
                    created += 1
            except Exception as e:
                failed += 1
                log_lines.append(f"Row {row}: {e}")
        return created, updated, failed, "\n".join(log_lines)

    def _import_inventory(self, rows):
        created, updated, failed = 0, 0, 0
        log_lines = []
        for row in rows:
            try:
                code, loc_path, qty, lot_name = (row + ["", "", "0", ""])[:4]
                product = self.env["product.product"].search(
                    [("default_code", "=", code)], limit=1,
                )
                location = self.env["stock.location"].search(
                    [("complete_name", "=", loc_path)], limit=1,
                )
                if not product or not location:
                    failed += 1
                    log_lines.append(f"Row {row}: product or location not found")
                    continue
                lot = False
                if lot_name and product.tracking == "lot":
                    lot = self.env["stock.lot"].search([
                        ("product_id", "=", product.id),
                        ("name", "=", lot_name),
                    ], limit=1) or self.env["stock.lot"].create({
                        "product_id": product.id,
                        "name": lot_name,
                        "company_id": location.company_id.id or 1,
                    })
                self.env["stock.quant"]._update_available_quantity(
                    product, location, float(qty), lot_id=lot,
                )
                created += 1
            except Exception as e:
                failed += 1
                log_lines.append(f"Row {row}: {e}")
        return created, updated, failed, "\n".join(log_lines)
