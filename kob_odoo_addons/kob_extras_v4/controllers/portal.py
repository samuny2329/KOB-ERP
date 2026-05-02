# -*- coding: utf-8 -*-
"""Phase 46 — B2B portal customization."""
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class KobB2BPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if "kob_open_quotes" in counters:
            values["kob_open_quotes"] = request.env["sale.order"].search_count([
                ("partner_id", "=", partner.id),
                ("state", "in", ["draft", "sent"]),
            ])
        if "kob_open_invoices" in counters:
            values["kob_open_invoices"] = request.env["account.move"].search_count([
                ("partner_id", "=", partner.id),
                ("move_type", "=", "out_invoice"),
                ("payment_state", "in", ["not_paid", "partial"]),
            ])
        return values

    @http.route(["/my/kob/dashboard"], type="http", auth="user", website=True)
    def kob_b2b_dashboard(self, **kw):
        partner = request.env.user.partner_id
        ytd_orders = request.env["sale.order"].search([
            ("partner_id", "=", partner.id),
            ("state", "in", ["sale", "done"]),
        ])
        recent_invoices = request.env["account.move"].search([
            ("partner_id", "=", partner.id),
            ("move_type", "=", "out_invoice"),
        ], limit=10, order="invoice_date desc")
        values = {
            "page_name": "kob_b2b_dashboard",
            "partner": partner,
            "ytd_count": len(ytd_orders),
            "ytd_total": sum(ytd_orders.mapped("amount_total")),
            "recent_invoices": recent_invoices,
        }
        return request.render("kob_extras_v4.portal_b2b_dashboard", values)

    @http.route(["/my/kob/reorder/<int:order_id>"], type="http",
                auth="user", website=True, csrf=False)
    def kob_quick_reorder(self, order_id, **kw):
        original = request.env["sale.order"].sudo().browse(order_id)
        if not original or original.partner_id != request.env.user.partner_id:
            return request.redirect("/my")
        new_so = request.env["sale.order"].sudo().create({
            "partner_id": original.partner_id.id,
            "origin": f"Reorder of {original.name}",
            "order_line": [
                (0, 0, {
                    "product_id": ln.product_id.id,
                    "product_uom_qty": ln.product_uom_qty,
                    "name": ln.name,
                })
                for ln in original.order_line if ln.product_id
            ],
        })
        return request.redirect(f"/my/orders/{new_so.id}")
