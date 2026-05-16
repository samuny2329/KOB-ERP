from odoo import api, fields, models


class ThitiPlanResourceLoad(models.Model):
    _name = "thiti.plan.resource.load"
    _description = "Thiti Resource Utilization per bucket"
    _order = "run_id, resource_id, bucket_start"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    resource_id = fields.Many2one("thiti.resource", index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", index=True)
    bucket_start = fields.Datetime(index=True)
    bucket_end = fields.Datetime(index=True)
    bucket_label = fields.Char()
    available_hours = fields.Float()
    loaded_hours = fields.Float()
    free_hours = fields.Float(compute="_compute_free", store=True)
    utilization_pct = fields.Float(compute="_compute_util", store=True)
    setup_hours = fields.Float()
    units_processed = fields.Float()

    @api.depends("available_hours", "loaded_hours")
    def _compute_free(self):
        for rec in self:
            rec.free_hours = max((rec.available_hours or 0.0) - (rec.loaded_hours or 0.0), 0.0)

    @api.depends("available_hours", "loaded_hours")
    def _compute_util(self):
        for rec in self:
            avail = rec.available_hours or 0.0
            rec.utilization_pct = (
                (rec.loaded_hours or 0.0) / avail * 100.0 if avail > 0 else 0.0
            )
