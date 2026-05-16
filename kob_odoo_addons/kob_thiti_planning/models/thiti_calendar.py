from odoo import _, fields, models


class ThitiCalendar(models.Model):
    _name = "thiti.calendar"
    _description = "Thiti Planning Calendar"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(index=True)
    default_value = fields.Float(
        default=1.0,
        help="Default value when no bucket is active (1=available, 0=unavailable).",
    )
    resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Linked Odoo Calendar", index=True,
    )
    bucket_ids = fields.One2many(
        "thiti.calendar.bucket", "calendar_id", "Buckets",
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Calendar name must be unique per company.")),
    ]
