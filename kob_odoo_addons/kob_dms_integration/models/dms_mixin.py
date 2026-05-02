# -*- coding: utf-8 -*-
"""Shared mixin for any model that wants a DMS smart button.

Sub-models declare:
  _dms_parent_folder = "Vendors" | "Customers" | "Employees" | "Assets"
  _dms_record_label_field = "name" or computed _get_dms_label()
"""
from odoo import api, fields, models


class KobDmsMixin(models.AbstractModel):
    _name = "kob.dms.mixin"
    _description = "DMS attach mixin"

    # Override on each consumer
    _dms_parent_folder = "Operations"  # default fallback

    dms_directory_id = fields.Many2one(
        "dms.directory", string="DMS Folder",
        compute="_compute_dms_directory_id",
        store=False,
        help="Auto-created folder in KOB Documents > <_dms_parent_folder> "
             "named after this record.",
    )
    dms_file_count = fields.Integer(
        compute="_compute_dms_directory_id", string="Documents",
    )

    def _get_dms_label(self):
        """Override per model — return display name for the per-record folder."""
        self.ensure_one()
        return self.display_name

    def _compute_dms_directory_id(self):
        for rec in self:
            rec.dms_directory_id = False
            rec.dms_file_count = 0
            if not rec.id:
                continue
            parent = self.env["dms.directory"].search([
                ("name", "=", rec._dms_parent_folder),
                ("parent_id.is_root_directory", "=", True),
            ], limit=1)
            if not parent:
                continue
            label = rec._get_dms_label()
            d = self.env["dms.directory"].search([
                ("name", "=", label),
                ("parent_id", "=", parent.id),
            ], limit=1)
            if d:
                rec.dms_directory_id = d.id
                rec.dms_file_count = self.env["dms.file"].search_count(
                    [("directory_id", "=", d.id)],
                )

    def action_open_dms_folder(self):
        """Auto-create the per-record dir if missing, then open it."""
        self.ensure_one()
        parent = self.env["dms.directory"].search([
            ("name", "=", self._dms_parent_folder),
            ("parent_id.is_root_directory", "=", True),
        ], limit=1)
        if not parent:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "DMS not configured",
                    "message": (
                        f"Parent folder '{self._dms_parent_folder}' does not "
                        "exist under KOB Documents root. "
                        "Run setup_dms_hierarchy.py first."
                    ),
                    "sticky": False,
                    "type": "warning",
                },
            }
        label = self._get_dms_label()
        d = self.env["dms.directory"].search([
            ("name", "=", label),
            ("parent_id", "=", parent.id),
        ], limit=1)
        if not d:
            d = self.env["dms.directory"].sudo().create({
                "name": label,
                "parent_id": parent.id,
                "is_root_directory": False,
                "company_id": self.company_id.id if hasattr(self, "company_id") and self.company_id else 1,
            })
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {label}",
            "res_model": "dms.file",
            "view_mode": "kanban,list,form",
            "domain": [("directory_id", "=", d.id)],
            "context": {
                "default_directory_id": d.id,
                "default_storage_id": d.storage_id.id if d.storage_id else False,
            },
            "target": "current",
        }
