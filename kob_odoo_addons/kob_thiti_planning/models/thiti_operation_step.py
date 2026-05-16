from odoo import _, fields, models


class ThitiOperationStep(models.Model):
    _name = "thiti.operation.step"
    _description = "Thiti Operation Step (sub-operation in routing)"
    _order = "operation_id, priority"

    operation_id = fields.Many2one(
        "thiti.operation", required=True, index=True, ondelete="cascade",
    )
    name = fields.Char(required=True)
    priority = fields.Integer(default=1)
    duration_hours = fields.Float(string="Fixed Duration (h)")
    duration_per_hours = fields.Float(string="Time per Unit (h)")
    resource_id = fields.Many2one("thiti.resource", index=True)
    routing_workcenter_id = fields.Many2one(
        "mrp.routing.workcenter", string="Linked Routing Step", index=True,
    )
    note = fields.Text()
