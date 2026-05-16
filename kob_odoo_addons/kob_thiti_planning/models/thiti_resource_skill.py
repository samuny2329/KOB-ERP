from odoo import _, fields, models


class ThitiResourceSkill(models.Model):
    _name = "thiti.resource.skill"
    _description = "Thiti Resource Skill (link)"
    _order = "resource_id, priority, skill_id"

    resource_id = fields.Many2one(
        "thiti.resource", required=True, index=True, ondelete="cascade",
    )
    skill_id = fields.Many2one(
        "thiti.skill", required=True, index=True, ondelete="restrict",
    )
    priority = fields.Integer(default=1)
    effective_start = fields.Datetime()
    effective_end = fields.Datetime()

    _sql_constraints = [
        ("resource_skill_unique", "UNIQUE(resource_id, skill_id)",
         _("Same skill assigned twice to one resource.")),
    ]
