from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ThitiCalendarBucket(models.Model):
    _name = "thiti.calendar.bucket"
    _description = "Thiti Calendar Bucket"
    _order = "calendar_id, priority desc, start_date"

    calendar_id = fields.Many2one(
        "thiti.calendar", required=True, index=True, ondelete="cascade",
    )
    name = fields.Char()
    start_date = fields.Datetime(required=True)
    end_date = fields.Datetime(required=True)
    value = fields.Float(
        default=1.0,
        help="Active value during this bucket (1=available, 0=unavailable).",
    )
    priority = fields.Integer(
        default=0,
        help="Higher priority overrides lower when buckets overlap.",
    )
    monday = fields.Boolean(default=True)
    tuesday = fields.Boolean(default=True)
    wednesday = fields.Boolean(default=True)
    thursday = fields.Boolean(default=True)
    friday = fields.Boolean(default=True)
    saturday = fields.Boolean(default=True)
    sunday = fields.Boolean(default=True)
    starttime_seconds = fields.Integer(
        default=0,
        help="Daily start time in seconds (0-86400). 0=midnight.",
    )
    endtime_seconds = fields.Integer(
        default=86400,
        help="Daily end time in seconds (0-86400). 86400=end of day.",
    )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date >= rec.end_date:
                raise ValidationError(_("Start date must be before end date."))
