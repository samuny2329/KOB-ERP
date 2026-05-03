# -*- coding: utf-8 -*-
"""Require attachment on purchase order before confirm."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    attachment_count = fields.Integer(
        compute="_compute_attachment_count")

    def _compute_attachment_count(self):
        Att = self.env["ir.attachment"]
        for r in self:
            r.attachment_count = Att.sudo().search_count([
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", r.id),
            ])

    def button_confirm(self):
        for r in self:
            if not r.attachment_count:
                raise UserError(_(
                    "ต้องแนบเอกสาร / ใบเสนอราคา อย่างน้อย 1 ไฟล์ "
                    "ก่อนยืนยัน Purchase Order %(name)s\n\n"
                    "กด 📎 ที่ chatter เพื่อแนบไฟล์",
                    name=r.name))
        return super().button_confirm()
