from odoo import fields, models


class ThitiPlanDemandPeg(models.Model):
    _name = "thiti.plan.demand.peg"
    _description = "Thiti Demand Pegging (which operation serves which demand)"
    _order = "run_id, demand_id"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    demand_id = fields.Many2one("thiti.demand", index=True)
    demand_name = fields.Char(index=True)
    plan_operation_id = fields.Many2one(
        "thiti.plan.operation", index=True, ondelete="set null",
    )
    operation_reference = fields.Char(index=True)
    item_id = fields.Many2one("thiti.item", index=True)
    location_id = fields.Many2one("thiti.location", index=True)
    quantity = fields.Float()
    due = fields.Datetime()
    plan_end = fields.Datetime()
    delay_days = fields.Float(
        help="Delay between plan_end and due (positive = late delivery).",
    )
    level = fields.Integer(
        help="Pegging depth (0 = direct, deeper = upstream operations).",
    )
