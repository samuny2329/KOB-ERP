# -*- coding: utf-8 -*-
"""Phase 42 — Customer self-service kiosk."""
from odoo import api, fields, models


class KobKioskSession(models.Model):
    _name = "kob.kiosk.session"
    _description = "KOB Kiosk Session"
    _order = "started_at desc"

    name = fields.Char(default=lambda s: s._default_name(), readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer")
    phone = fields.Char()
    started_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    ended_at = fields.Datetime(readonly=True)
    state = fields.Selection(
        [("active", "Active"), ("ordered", "Ordered"),
         ("checked_in", "Checked In"), ("closed", "Closed")],
        default="active",
    )
    purpose = fields.Selection(
        [("browse", "Browse Catalog"),
         ("checkin", "Check-in / Loyalty"),
         ("order", "Place Order"),
         ("support", "Support Request")],
        default="browse",
    )
    sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    note = fields.Text()
    device_id = fields.Char(help="Kiosk device identifier")

    @api.model
    def _default_name(self):
        seq = self.env["ir.sequence"].next_by_code("kob.kiosk.session") or "/"
        return f"KIOSK/{seq}"

    def action_close(self):
        for r in self:
            r.write({"state": "closed", "ended_at": fields.Datetime.now()})

    def action_create_order(self):
        self.ensure_one()
        if not self.partner_id:
            return False
        so = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "origin": self.name,
        })
        self.write({"sale_order_id": so.id, "state": "ordered"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": so.id,
            "view_mode": "form",
            "target": "current",
        }
