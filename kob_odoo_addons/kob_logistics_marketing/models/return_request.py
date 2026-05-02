# -*- coding: utf-8 -*-
"""Phase 50 — Returns logistics workflow.

State machine: draft → approved → picked_up → received → inspected →
(restocked | scrapped | refunded). One request can have multiple lines.
"""
from odoo import api, fields, models, _


class KobReturnRequest(models.Model):
    _name = "kob.return.request"
    _description = "Return Request (RMA)"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default=lambda s: s._default_name(), readonly=True)
    sale_order_id = fields.Many2one("sale.order", required=True)
    partner_id = fields.Many2one(related="sale_order_id.partner_id", store=True)
    state = fields.Selection(
        [("draft", "Draft"),
         ("submitted", "Submitted"),
         ("approved", "Approved"),
         ("picked_up", "Picked Up"),
         ("received", "Received"),
         ("inspected", "Inspected"),
         ("restocked", "Restocked"),
         ("refunded", "Refunded"),
         ("rejected", "Rejected")],
        default="draft", tracking=True,
    )
    reason_code = fields.Selection(
        [("damaged", "Damaged on Arrival"),
         ("wrong_item", "Wrong Item Shipped"),
         ("not_as_described", "Not as Described"),
         ("buyer_remorse", "Changed Mind"),
         ("size_fit", "Size / Fit Issue"),
         ("expired", "Expired / Near Expiry"),
         ("quality", "Quality Issue"),
         ("other", "Other")],
        required=True,
    )
    pickup_carrier_id = fields.Many2one("kob.shipping.carrier")
    pickup_shipment_id = fields.Many2one("kob.shipment")
    refund_method = fields.Selection(
        [("original", "Refund to Original Payment"),
         ("store_credit", "Store Credit"),
         ("exchange", "Exchange"),
         ("none", "No Refund")],
        default="original",
    )
    refund_amount = fields.Float(compute="_compute_refund_amount", store=True)
    line_ids = fields.One2many("kob.return.request.line", "request_id")
    description = fields.Text(string="Customer Description")
    inspection_notes = fields.Text()

    @api.model
    def _default_name(self):
        seq = self.env["ir.sequence"].next_by_code("kob.return.request") or "/"
        return f"RMA/{seq}"

    @api.depends("line_ids.refund_subtotal")
    def _compute_refund_amount(self):
        for r in self:
            r.refund_amount = sum(r.line_ids.mapped("refund_subtotal"))

    def action_submit(self):
        for r in self:
            if not r.line_ids:
                raise self.env["ir.exceptions"].UserError(
                    _("Add at least one return line before submitting."))
            r.state = "submitted"

    def action_approve(self):
        for r in self:
            r.state = "approved"
            r.message_post(body=_("RMA approved."))

    def action_picked_up(self):
        self.write({"state": "picked_up"})

    def action_received(self):
        self.write({"state": "received"})

    def action_inspect(self):
        self.write({"state": "inspected"})

    def action_restock(self):
        for r in self:
            for ln in r.line_ids.filtered(lambda l: l.condition == "good"):
                ln.product_id.with_context(
                    location=ln.return_to_location_id.id
                )  # plugin: actual stock move
            r.state = "restocked"

    def action_refund(self):
        # Plugin: create credit note
        self.write({"state": "refunded"})

    def action_reject(self):
        self.write({"state": "rejected"})


class KobReturnRequestLine(models.Model):
    _name = "kob.return.request.line"
    _description = "Return Request Line"

    request_id = fields.Many2one("kob.return.request", required=True,
                                 ondelete="cascade")
    sale_order_line_id = fields.Many2one("sale.order.line")
    product_id = fields.Many2one("product.product", required=True)
    quantity = fields.Float(required=True, default=1)
    unit_price = fields.Float()
    refund_subtotal = fields.Float(compute="_compute_subtotal", store=True)
    condition = fields.Selection(
        [("good", "Good — Restock"),
         ("damaged", "Damaged — Scrap"),
         ("missing", "Missing")],
        default="good",
    )
    return_to_location_id = fields.Many2one("stock.location",
                                            string="Return Location")
    notes = fields.Text()

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for r in self:
            r.refund_subtotal = (r.quantity or 0) * (r.unit_price or 0)
