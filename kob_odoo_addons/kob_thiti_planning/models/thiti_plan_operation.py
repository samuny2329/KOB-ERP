from odoo import _, api, fields, models


OP_STATUS = [
    ("proposed", "Proposed"),
    ("approved", "Approved"),
    ("confirmed", "Confirmed"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("closed", "Closed"),
]


class ThitiPlanOperation(models.Model):
    _name = "thiti.plan.operation"
    _description = "Thiti Plan Operation (solver output)"
    _order = "start_datetime, run_id"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    reference = fields.Char(index=True)
    operation_name = fields.Char(index=True)
    item_id = fields.Many2one("thiti.item", index=True)
    product_id = fields.Many2one(
        "product.product", index=True,
        help="Resolved Odoo product (from item name reverse lookup).",
    )
    location_id = fields.Many2one("thiti.location", index=True)
    quantity = fields.Float()
    start_datetime = fields.Datetime(index=True)
    end_datetime = fields.Datetime(index=True)
    duration_hours = fields.Float(compute="_compute_duration", store=True)
    resource_id = fields.Many2one("thiti.resource", index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", index=True)
    op_type = fields.Selection(
        [("po", "Purchase"),
         ("mo", "Manufacturing"),
         ("do", "Distribution"),
         ("dlvr", "Delivery"),
         ("routing", "Routing step")],
        string="Op Type",
    )
    status = fields.Selection(OP_STATUS, default="proposed", index=True)
    criticality = fields.Float()
    delay_days = fields.Float()
    bom_id = fields.Many2one("mrp.bom", index=True)
    note = fields.Text()

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                delta = rec.end_datetime - rec.start_datetime
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0
