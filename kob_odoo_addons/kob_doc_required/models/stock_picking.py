# -*- coding: utf-8 -*-
"""Require attachment on receipt/delivery before validate."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    attachment_count = fields.Integer(
        string="Attachments", compute="_compute_attachment_count")
    requires_doc = fields.Boolean(
        string="Photo / File Required",
        compute="_compute_requires_doc", store=False,
        help="Auto-flagged for incoming/outgoing transfers; user must "
             "attach at least one photo or file before validate.")

    @api.depends("picking_type_id")
    def _compute_requires_doc(self):
        # Exempt KOB WMS-driven pickings (Pick/Pack/Outbound/Dispatch
        # screens will use camera capture later — no manual attach needed).
        WmsSO = self.env.get("wms.sales.order")
        for r in self:
            base = bool(
                r.picking_type_id and r.picking_type_id.code in
                ("incoming", "outgoing"))
            wms_linked = False
            if WmsSO is not None and r.id:
                wms_linked = bool(WmsSO.sudo().search_count(
                    [("picking_id", "=", r.id)]))
            r.requires_doc = base and not wms_linked

    def _compute_attachment_count(self):
        Att = self.env["ir.attachment"]
        for r in self:
            r.attachment_count = Att.sudo().search_count([
                ("res_model", "=", "stock.picking"),
                ("res_id", "=", r.id),
            ])

    def button_validate(self):
        # WMS uses these context flags when validating from Pack screen —
        # treat as bypass for the document requirement.
        ctx = self.env.context or {}
        wms_bypass = (ctx.get("skip_immediate") or
                      ctx.get("skip_backorder") or
                      ctx.get("skip_doc_check"))
        if not wms_bypass:
            for r in self:
                if r.requires_doc and not r.attachment_count:
                    raise UserError(_(
                        "ต้องแนบเอกสาร / ภาพถ่ายอย่างน้อย 1 ไฟล์ "
                        "ก่อน validate การ %(label)s นี้\n\n"
                        "กด 📎 ที่ chatter เพื่อแนบไฟล์",
                        label=(_("รับสินค้า") if r.picking_type_id.code == "incoming"
                               else _("ส่งสินค้า"))))
        return super().button_validate()

    def action_open_attachment_picker(self):
        """Helper button to scroll to chatter / open attachment picker."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("res_model", "=", "stock.picking"),
                       ("res_id", "=", self.id)],
            "context": {"default_res_model": "stock.picking",
                        "default_res_id": self.id},
            "target": "new",
        }
