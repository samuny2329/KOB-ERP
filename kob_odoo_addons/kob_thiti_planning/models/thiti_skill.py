from odoo import _, fields, models


class ThitiSkill(models.Model):
    _name = "thiti.skill"
    _description = "Thiti Resource Skill"
    _order = "name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    note = fields.Text()
    active = fields.Boolean(default=True)
    resource_count = fields.Integer(compute="_compute_resource_count")

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", _("Skill name must be unique.")),
    ]

    def _compute_resource_count(self):
        groups = self.env["thiti.resource.skill"]._read_group(
            [("skill_id", "in", self.ids)],
            groupby=["skill_id"],
            aggregates=["__count"],
        )
        counts = {skill.id: count for skill, count in groups}
        for rec in self:
            rec.resource_count = counts.get(rec.id, 0)
