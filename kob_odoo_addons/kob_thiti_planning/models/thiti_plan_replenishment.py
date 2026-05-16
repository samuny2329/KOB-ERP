from odoo import _, fields, models


REPLEN_KIND = [
    ("po", "Purchase Order"),
    ("mo", "Manufacturing Order"),
    ("do", "Distribution Order"),
]

REPLEN_STATE = [
    ("proposed", "Proposed"),
    ("created", "Draft Created"),
    ("confirmed", "Confirmed"),
    ("canceled", "Canceled"),
    ("done", "Done"),
]


class ThitiPlanReplenishment(models.Model):
    _name = "thiti.plan.replenishment"
    _description = "Thiti Replenishment Proposal (PO/MO/DO from solver)"
    _inherit = ["mail.thread"]
    _order = "run_id, kind, scheduled_date"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    plan_operation_id = fields.Many2one(
        "thiti.plan.operation", index=True, ondelete="set null",
    )
    kind = fields.Selection(REPLEN_KIND, required=True, index=True)
    state = fields.Selection(REPLEN_STATE, default="proposed", index=True, tracking=True)
    item_id = fields.Many2one("thiti.item", index=True)
    product_id = fields.Many2one("product.product", index=True)
    location_id = fields.Many2one("thiti.location", index=True)
    warehouse_id = fields.Many2one("stock.warehouse", index=True)
    source_warehouse_id = fields.Many2one("stock.warehouse")
    supplier_id = fields.Many2one("thiti.supplier", index=True)
    partner_id = fields.Many2one("res.partner", index=True)
    bom_id = fields.Many2one("mrp.bom", index=True)
    quantity = fields.Float(required=True)
    uom_id = fields.Many2one("uom.uom")
    scheduled_date = fields.Datetime(index=True)
    due_date = fields.Datetime()
    cost = fields.Monetary()
    currency_id = fields.Many2one("res.currency",
                                  default=lambda s: s.env.company.currency_id)
    origin = fields.Char(
        required=True, index=True,
        help="Tag stored on created PO/MO/Picking for idempotent re-runs.",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", index=True, readonly=True,
    )
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line", index=True, readonly=True,
    )
    production_id = fields.Many2one(
        "mrp.production", index=True, readonly=True,
    )
    picking_id = fields.Many2one(
        "stock.picking", index=True, readonly=True,
    )
    error_message = fields.Text(readonly=True)

    def action_open_target(self):
        self.ensure_one()
        if self.purchase_order_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "purchase.order",
                "res_id": self.purchase_order_id.id,
                "view_mode": "form",
            }
        if self.production_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "mrp.production",
                "res_id": self.production_id.id,
                "view_mode": "form",
            }
        if self.picking_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "stock.picking",
                "res_id": self.picking_id.id,
                "view_mode": "form",
            }
        return False
