from odoo import _, fields, models


FLOW_TYPE = [
    ("start", "Start (consume at start)"),
    ("end", "End (produce at end)"),
    ("transfer_batch", "Transfer Batch"),
    ("fixed_start", "Fixed Start"),
    ("fixed_end", "Fixed End"),
]


class ThitiFlow(models.Model):
    _name = "thiti.flow"
    _description = "Thiti Flow (operation ↔ buffer material movement)"
    _order = "operation_id, item_id"

    operation_id = fields.Many2one(
        "thiti.operation", required=True, index=True, ondelete="cascade",
    )
    item_id = fields.Many2one(
        "thiti.item", required=True, index=True, ondelete="restrict",
    )
    location_id = fields.Many2one("thiti.location", index=True)
    flow_type = fields.Selection(FLOW_TYPE, default="start", required=True)
    quantity = fields.Float(
        default=-1.0,
        help="Negative=consumption, positive=production.",
    )
    quantity_fixed = fields.Float(
        default=0.0,
        help="Fixed quantity per operation regardless of size.",
    )
    priority = fields.Integer(default=1)
    name_alt = fields.Char(string="Alternate Group")
    search_mode = fields.Selection(
        [("priority", "Priority"), ("minlateness", "Min Lateness")],
        default="priority",
    )
    effective_start = fields.Datetime()
    effective_end = fields.Datetime()
