# -*- coding: utf-8 -*-
"""Phase 49 — Shipment label printing + tracking aggregation.

Each `kob.shipment` is a single physical parcel with one carrier-assigned
tracking number. Picking → shipment is 1:N (one delivery order can be split
into multiple parcels). Tracking events are pulled per cron + on-demand.
"""
from odoo import api, fields, models


class KobShipment(models.Model):
    _name = "kob.shipment"
    _description = "Shipment"
    _order = "create_date desc"
    _inherit = ["mail.thread"]
    _rec_name = "tracking_number"

    name = fields.Char(default=lambda s: s._default_name(), readonly=True)
    picking_id = fields.Many2one("stock.picking", string="Delivery Order",
                                 ondelete="cascade")
    sale_order_id = fields.Many2one(related="picking_id.sale_id",
                                    string="Sale Order", store=True)
    partner_id = fields.Many2one("res.partner", string="Customer",
                                 related="picking_id.partner_id", store=True)
    carrier_id = fields.Many2one("kob.shipping.carrier", required=True)
    rate_id = fields.Many2one("kob.shipping.rate")
    service = fields.Char()
    tracking_number = fields.Char(tracking=True, index=True)
    label_data = fields.Binary(string="Label PDF", attachment=True)
    label_filename = fields.Char()
    weight_kg = fields.Float()
    declared_value = fields.Float()
    cod_amount = fields.Float()
    is_cod = fields.Boolean(compute="_compute_is_cod", store=True)
    state = fields.Selection(
        [("draft", "Draft"),
         ("ready", "Label Ready"),
         ("picked_up", "Picked Up"),
         ("in_transit", "In Transit"),
         ("out_for_delivery", "Out for Delivery"),
         ("delivered", "Delivered"),
         ("returned", "Returned"),
         ("failed", "Failed")],
        default="draft", tracking=True,
    )
    estimated_delivery_date = fields.Date()
    actual_delivery_date = fields.Date()
    last_tracked_at = fields.Datetime()
    event_ids = fields.One2many("kob.shipment.event", "shipment_id")
    notes = fields.Text()

    @api.model
    def _default_name(self):
        seq = self.env["ir.sequence"].next_by_code("kob.shipment") or "/"
        return f"SHIP/{seq}"

    @api.depends("cod_amount")
    def _compute_is_cod(self):
        for r in self:
            r.is_cod = r.cod_amount and r.cod_amount > 0

    def action_request_label(self):
        """Stub — call carrier API in plugin override."""
        for r in self:
            if not r.tracking_number:
                # Generate a fake tracking for demo
                code = r.carrier_id.code or "XX"
                r.tracking_number = f"{code.upper()}{r.id:08d}"
            r.state = "ready"
            r.message_post(body="Label requested (stub).")

    def action_track(self):
        """Stub — pull events from carrier API in plugin override."""
        Event = self.env["kob.shipment.event"]
        for r in self:
            if not r.tracking_number:
                continue
            r.last_tracked_at = fields.Datetime.now()
            # Stub: don't create fake events; real impl calls API

    @api.model
    def cron_track_active(self):
        active = self.search([("state", "in",
                              ["ready", "picked_up", "in_transit",
                               "out_for_delivery"])])
        active.action_track()
        return len(active)


class KobShipmentEvent(models.Model):
    _name = "kob.shipment.event"
    _description = "Shipment Tracking Event"
    _order = "event_at desc"

    shipment_id = fields.Many2one("kob.shipment", required=True,
                                  ondelete="cascade")
    event_at = fields.Datetime(default=fields.Datetime.now, required=True)
    status = fields.Char()
    location = fields.Char()
    description = fields.Text()
    raw_payload = fields.Text()
