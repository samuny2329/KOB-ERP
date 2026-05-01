# -*- coding: utf-8 -*-
"""SO extensions: P2D, credit gate, platform bridge, intercompany hook."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    promise_date = fields.Date(
        readonly=True,
        help="Computed promise-to-deliver date.",
    )
    p2d_confidence = fields.Float(
        digits=(3, 2), readonly=True,
        help="Confidence score 0..1 of the promise date.",
    )
    platform_bridge_ids = fields.One2many(
        "kob.platform.order.bridge", "sale_order_id",
        string="Platform Orders",
    )
    intercompany_transfer_ids = fields.One2many(
        "kob.intercompany.transfer", "sales_order_id",
        string="Intercompany Mirrors",
    )

    def action_compute_promise_date(self):
        """Promise-to-deliver heuristic: lead = 4d default; +5d if any
        SKU is short; confidence drops to 0.55 when short, 0.85 otherwise.
        Blocked partner → 0.30 confidence regardless."""
        for so in self:
            today = fields.Date.context_today(so)
            short = False
            for line in so.order_line:
                if line.product_id and line.product_id.qty_available < float(
                    line.product_uom_qty or 0,
                ):
                    short = True
                    break
            base = 4
            if short:
                base += 5
                conf = 0.55
            else:
                conf = 0.85
            if so.partner_id.blocked:
                conf = 0.30
            so.promise_date = today + timedelta(days=base)
            so.p2d_confidence = conf

    def _check_customer_credit(self):
        """Block confirmation when customer is on hold or over limit."""
        for so in self:
            partner = so.partner_id
            if partner.blocked:
                raise UserError(_(
                    "Customer %s is blocked: %s"
                ) % (partner.display_name, partner.blocked_reason or ""))
            if partner.credit_limit and partner.credit_limit > 0:
                exposure = float(partner.credit or 0) + float(so.amount_total)
                if exposure > partner.credit_limit:
                    raise UserError(_(
                        "Customer %s would exceed credit limit "
                        "(%s + %s > %s)."
                    ) % (
                        partner.display_name, partner.credit,
                        so.amount_total, partner.credit_limit,
                    ))
        return True

    def action_confirm(self):
        self._check_customer_credit()
        return super().action_confirm()
