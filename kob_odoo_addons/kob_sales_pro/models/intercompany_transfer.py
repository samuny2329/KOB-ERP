# -*- coding: utf-8 -*-
"""Intercompany transfer — when company A's SO ships from company B's WH."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobIntercompanyTransfer(models.Model):
    _name = "kob.intercompany.transfer"
    _description = "Intercompany SO/PO Mirror"
    _order = "create_date desc"

    sales_order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True,
    )
    so_company_id = fields.Many2one(
        "res.company", string="SO Company", required=True,
    )
    fulfillment_company_id = fields.Many2one(
        "res.company", string="Fulfillment Company", required=True,
    )
    mirror_po_id = fields.Many2one(
        "purchase.order", string="Mirror PO", ondelete="set null",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("mirrored", "Mirrored"),
            ("settled", "Settled"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    transfer_amount = fields.Monetary(currency_field="currency_id")
    transfer_pricing_method = fields.Selection(
        [
            ("cost_plus", "Cost-plus"),
            ("list_price", "List price"),
            ("manual", "Manual"),
        ],
        default="cost_plus",
        required=True,
    )
    transfer_pricing_pct = fields.Float(
        digits=(6, 2), default=0,
        help="Markup % applied for cost-plus.",
    )
    settled_at = fields.Datetime(readonly=True)
    note = fields.Text()
    currency_id = fields.Many2one(
        related="sales_order_id.currency_id", store=True, readonly=True,
    )

    @api.constrains("so_company_id", "fulfillment_company_id")
    def _check_companies_differ(self):
        for rec in self:
            if rec.so_company_id == rec.fulfillment_company_id:
                raise UserError(
                    _("SO company and fulfillment company must differ.")
                )

    def action_mirror(self):
        """Create the mirror PO in the fulfillment company."""
        for tr in self:
            if tr.state != "draft":
                raise UserError(_("Only draft transfers can be mirrored."))
            so = tr.sales_order_id
            base = sum(so.order_line.mapped("price_subtotal"))
            if tr.transfer_pricing_method == "cost_plus":
                amt = base * (1.0 + (tr.transfer_pricing_pct or 0) / 100.0)
            elif tr.transfer_pricing_method == "list_price":
                amt = sum(
                    line.product_id.list_price * line.product_uom_qty
                    for line in so.order_line
                )
            else:
                amt = tr.transfer_amount
            tr.transfer_amount = amt

            # Create mirror PO in the fulfillment company.
            po_vals = {
                "partner_id": tr.so_company_id.partner_id.id,
                "company_id": tr.fulfillment_company_id.id,
                "origin": "Intercompany %s" % so.name,
                "order_line": [
                    (0, 0, {
                        "product_id": line.product_id.id,
                        "name": line.name,
                        "product_qty": line.product_uom_qty,
                        "product_uom_id": line.product_uom.id,
                        "price_unit": (
                            float(line.price_subtotal)
                            * (1.0 + (tr.transfer_pricing_pct or 0) / 100.0)
                            / float(line.product_uom_qty or 1)
                        ),
                        "date_planned": fields.Datetime.now(),
                    })
                    for line in so.order_line
                ],
            }
            po = self.env["purchase.order"].sudo().with_company(
                tr.fulfillment_company_id,
            ).create(po_vals)
            tr.mirror_po_id = po.id
            tr.state = "mirrored"

    def action_settle(self):
        for tr in self:
            if tr.state != "mirrored":
                raise UserError(_("Only mirrored transfers can be settled."))
            tr.write({
                "state": "settled",
                "settled_at": fields.Datetime.now(),
            })

    def action_cancel(self):
        for tr in self:
            if tr.state == "settled":
                raise UserError(_("Cannot cancel a settled transfer."))
            tr.state = "cancelled"
