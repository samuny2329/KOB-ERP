# -*- coding: utf-8 -*-
"""RMA — Return order header + line with state machine."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


RETURN_REASONS = [
    ("wrong_item", "Wrong item received"),
    ("damaged", "Damaged in transit"),
    ("defective", "Defective product"),
    ("not_as_described", "Not as described"),
    ("buyer_remorse", "Buyer's remorse"),
    ("expired", "Product expired"),
    ("duplicate", "Duplicate order"),
    ("other", "Other"),
]


class KobReturnOrder(models.Model):
    _name = "kob.return.order"
    _description = "Return Order (RMA)"
    _order = "requested_at desc"

    name = fields.Char(
        required=True, default=lambda s: _("New"), copy=False,
        readonly=True,
    )
    sales_order_id = fields.Many2one(
        "sale.order", required=True, ondelete="restrict",
        domain=[("state", "in", ("sale", "done"))],
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="sales_order_id.currency_id", store=True, readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("received", "Received"),
            ("restocked", "Restocked"),
            ("scrapped", "Scrapped"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    requested_at = fields.Datetime(default=fields.Datetime.now)
    received_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    receipt_location_id = fields.Many2one(
        "stock.location", domain=[("usage", "=", "internal")],
    )
    refund_amount = fields.Monetary(currency_field="currency_id")
    line_ids = fields.One2many("kob.return.order.line", "return_order_id")
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "kob.return.order"
                ) or "RMA/" + fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        return super().create(vals_list)

    def _check_transition(self, target):
        allowed = {
            "draft": {"received", "cancelled"},
            "received": {"restocked", "scrapped", "cancelled"},
        }
        for r in self:
            cur = r.state
            if cur not in allowed or target not in allowed[cur]:
                raise UserError(_(
                    "Cannot move return %s from '%s' to '%s'."
                ) % (r.name, cur, target))

    def action_receive(self):
        self._check_transition("received")
        self.write({"state": "received", "received_at": fields.Datetime.now()})

    def action_restock(self):
        self._check_transition("restocked")
        for r in self:
            if not r.receipt_location_id:
                raise UserError(_("Receipt location is required to restock."))
            for line in r.line_ids:
                line.qty_restocked = line.qty_returned
        self.write({
            "state": "restocked",
            "completed_at": fields.Datetime.now(),
        })

    def action_scrap(self):
        self._check_transition("scrapped")
        for r in self:
            for line in r.line_ids:
                line.qty_scrapped = line.qty_returned
        self.write({
            "state": "scrapped",
            "completed_at": fields.Datetime.now(),
        })

    def action_cancel(self):
        self._check_transition("cancelled")
        self.write({"state": "cancelled"})


class KobReturnOrderLine(models.Model):
    _name = "kob.return.order.line"
    _description = "Return Order Line"

    return_order_id = fields.Many2one(
        "kob.return.order", required=True, ondelete="cascade",
    )
    so_line_id = fields.Many2one("sale.order.line")
    product_id = fields.Many2one(
        "product.product", required=True,
    )
    qty_returned = fields.Float(digits="Product Unit of Measure")
    qty_restocked = fields.Float(digits="Product Unit of Measure")
    qty_scrapped = fields.Float(digits="Product Unit of Measure")
    reason_code = fields.Selection(
        RETURN_REASONS, default="other", required=True,
    )
    reason_note = fields.Char()
    refund_amount = fields.Monetary(currency_field="currency_id")
    lot_id = fields.Many2one("stock.lot")
    currency_id = fields.Many2one(
        related="return_order_id.currency_id", store=True, readonly=True,
    )
