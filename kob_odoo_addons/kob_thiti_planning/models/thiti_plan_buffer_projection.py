from odoo import fields, models


class ThitiPlanBufferProjection(models.Model):
    _name = "thiti.plan.buffer.projection"
    _description = "Thiti Buffer Inventory Projection over time"
    _order = "run_id, buffer_id, bucket_start"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    buffer_id = fields.Many2one("thiti.buffer", index=True)
    item_id = fields.Many2one("thiti.item", index=True)
    location_id = fields.Many2one("thiti.location", index=True)
    bucket_start = fields.Datetime(index=True)
    bucket_end = fields.Datetime(index=True)
    bucket_label = fields.Char()
    start_onhand = fields.Float()
    consumed = fields.Float()
    produced = fields.Float()
    end_onhand = fields.Float()
    safety_stock = fields.Float()
    below_safety = fields.Boolean(index=True)
    shortage_qty = fields.Float()
