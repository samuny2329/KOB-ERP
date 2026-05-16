from odoo import fields, models


PROBLEM_SEVERITY = [
    ("info", "Info"),
    ("warning", "Warning"),
    ("error", "Error"),
    ("critical", "Critical"),
]


class ThitiPlanProblem(models.Model):
    _name = "thiti.plan.problem"
    _description = "Thiti Plan Problem (overload, shortage, lateness, infeasibility)"
    _order = "run_id, severity desc, problem_type"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    problem_type = fields.Char(required=True, index=True)
    severity = fields.Selection(PROBLEM_SEVERITY, default="warning", index=True)
    entity_kind = fields.Selection(
        [("demand", "Demand"),
         ("buffer", "Buffer"),
         ("resource", "Resource"),
         ("operation", "Operation")],
        index=True,
    )
    entity_name = fields.Char(index=True)
    demand_id = fields.Many2one("thiti.demand", index=True)
    buffer_id = fields.Many2one("thiti.buffer", index=True)
    resource_id = fields.Many2one("thiti.resource", index=True)
    plan_operation_id = fields.Many2one(
        "thiti.plan.operation", index=True, ondelete="set null",
    )
    start_datetime = fields.Datetime()
    end_datetime = fields.Datetime()
    weight = fields.Float()
    description = fields.Text()
