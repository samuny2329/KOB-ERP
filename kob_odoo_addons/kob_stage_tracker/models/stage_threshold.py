from odoo import api, fields, models


class StageThreshold(models.Model):
    _name = "kob.stage.threshold"
    _description = "Alert if a record sits in a stage past the threshold"
    _order = "res_model, state_value, threshold_minutes"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    res_model = fields.Char(required=True, help="e.g. 'purchase.order'")
    state_field = fields.Char(
        default="state",
        help="Override if the stage field on this model is not 'state'.",
    )
    state_value = fields.Char(
        required=True,
        help="Stage value that, if held longer than threshold, triggers alert.",
    )
    threshold_minutes = fields.Integer(required=True, default=240)
    working_hours_only = fields.Boolean(default=True)
    severity = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    action_type = fields.Selection(
        [
            ("activity", "Mail Activity for owner"),
            ("battle_board", "Push to Battle Board"),
            ("discuss", "Post to Discuss channel"),
            ("ai", "Trigger AI agent run"),
        ],
        default="activity",
        required=True,
    )
    target_user_field = fields.Char(
        default="user_id",
        help="Field name on the record holding the owner res.users id.",
    )
    target_channel_id = fields.Many2one("discuss.channel")
    last_scan_at = fields.Datetime(readonly=True)
    last_scan_breaches = fields.Integer(readonly=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    @api.constrains("res_model", "state_field")
    def _check_model_field(self):
        for th in self:
            Model = self.env.get(th.res_model)
            if Model is None:
                continue
            if th.state_field and th.state_field not in Model._fields:
                from odoo.exceptions import ValidationError
                raise ValidationError(
                    f"Field {th.state_field!r} not found on {th.res_model!r}"
                )
