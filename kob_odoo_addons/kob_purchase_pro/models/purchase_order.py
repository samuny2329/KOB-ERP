# -*- coding: utf-8 -*-
"""Purchase Order: approval gating + budget link + KOB notes."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    note_internal = fields.Text(
        string="Internal Note",
        help="Visible to KOB staff only — never exposed on the vendor PDF.",
    )
    note_vendor = fields.Text(
        string="Vendor-facing Note",
        help="Printed on the PO/RFQ sent to the vendor.",
    )
    approval_state = fields.Selection(
        [
            ("not_required", "Not required"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="not_required",
        tracking=True,
    )
    approver_id = fields.Many2one("res.users", string="Approver", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    budget_id = fields.Many2one(
        "kob.procurement.budget",
        string="Procurement Budget",
        ondelete="set null",
    )
    resupply_picking_count = fields.Integer(
        compute="_compute_resupply_picking_count",
        string="Resupply Transfers",
    )
    has_resupply_products = fields.Boolean(
        compute="_compute_resupply_picking_count",
        help="True if at least one product on this PO has a route requiring "
             "downstream resupply (e.g. Resupply Subcontractor on Order, "
             "per-warehouse resupply routes).",
    )

    def _resupply_products(self):
        """Subset of products whose route_ids include at least one
        'Resupply' route — filter what the smart button counts."""
        self.ensure_one()
        return self.order_line.product_id.product_tmpl_id.filtered(
            lambda t: any(
                "resupply" in (r.name or "").lower() for r in t.route_ids
            )
        )

    @api.depends("order_line.product_id.product_tmpl_id.route_ids", "picking_ids.state")
    def _compute_resupply_picking_count(self):
        Picking = self.env["stock.picking"]
        for po in self:
            resupply_tmpls = po._resupply_products()
            po.has_resupply_products = bool(resupply_tmpls)
            received_locs = po.picking_ids.filtered(
                lambda p: p.state == "done"
            ).mapped("location_dest_id")
            if not received_locs or not resupply_tmpls:
                po.resupply_picking_count = 0
                continue
            po.resupply_picking_count = Picking.search_count([
                ("location_id", "in", received_locs.ids),
                ("picking_type_id.code", "=", "internal"),
                ("origin", "ilike", po.name),
                ("move_ids.product_id.product_tmpl_id", "in", resupply_tmpls.ids),
            ])

    def action_view_resupply(self):
        """Open internal transfers that move PO-received goods (filtered to
        products with Resupply rules) from main receiving location onward
        to other warehouses. If none yet, open create form pre-filled."""
        self.ensure_one()
        Picking = self.env["stock.picking"]
        resupply_tmpls = self._resupply_products()
        received_locs = self.picking_ids.filtered(
            lambda p: p.state == "done"
        ).mapped("location_dest_id")
        if not received_locs or not resupply_tmpls:
            domain = [("id", "=", 0)]
        else:
            domain = [
                ("location_id", "in", received_locs.ids),
                ("picking_type_id.code", "=", "internal"),
                ("origin", "ilike", self.name),
                ("move_ids.product_id.product_tmpl_id", "in", resupply_tmpls.ids),
            ]
        action = {
            "type": "ir.actions.act_window",
            "name": _("Resupply Transfers — %s") % self.name,
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": domain,
        }
        # Default values for create-new from this list
        warehouse = self.picking_type_id.warehouse_id
        if warehouse:
            int_pt = self.env["stock.picking.type"].search([
                ("warehouse_id", "=", warehouse.id),
                ("code", "=", "internal"),
            ], limit=1)
            if int_pt:
                action["context"] = {
                    "default_picking_type_id": int_pt.id,
                    "default_location_id": warehouse.lot_stock_id.id,
                    "default_origin": self.name,
                }
        return action

    def action_request_approval(self):
        for po in self:
            if po.state not in ("draft", "sent"):
                raise UserError(
                    _("Only draft / sent POs can be sent for approval."),
                )
            po.approval_state = "pending"

    def action_approve(self):
        for po in self:
            if po.approval_state != "pending":
                raise UserError(_("PO is not pending approval."))
            po.write({
                "approval_state": "approved",
                "approver_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })

    def action_reject(self):
        for po in self:
            if po.approval_state != "pending":
                raise UserError(_("PO is not pending approval."))
            po.approval_state = "rejected"

    def button_confirm(self):
        # Budget gate: if a budget is linked, ensure remaining ≥ amount_total.
        for po in self:
            if po.budget_id and po.budget_id.auto_block_overrun:
                remaining = po.budget_id.remaining_amount
                if po.amount_total > remaining:
                    if po.approval_state != "approved":
                        po.approval_state = "pending"
                        raise UserError(_(
                            "PO total %s exceeds budget remaining %s. "
                            "Approval required before confirming."
                        ) % (po.amount_total, remaining))
        return super().button_confirm()
