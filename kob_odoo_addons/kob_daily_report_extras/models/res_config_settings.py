from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    kob_dispatch_teams_webhook = fields.Char(
        string="MS Teams webhook (Dispatch)",
        config_parameter="kob_daily_report_extras.teams_webhook",
        help=(
            "Incoming webhook URL of the Microsoft Teams channel that "
            "receives the daily dispatch report. Get it from Teams > "
            "channel ⋯ > Connectors > Incoming Webhook. Leave blank to "
            "fall back to Discuss inbox only."
        ),
    )
    kob_dispatch_send_hour = fields.Integer(
        string="Send hour (0-23)",
        config_parameter="kob_daily_report_extras.send_hour",
        default=18,
        help="Hour of day the cron should run, in the company's timezone.",
    )
