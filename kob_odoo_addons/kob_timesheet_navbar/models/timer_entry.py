from odoo import api, fields, models


class KobTimerEntry(models.Model):
    """Lightweight timer entry. When stopped, posts to
    account.analytic.line if user picks a project/task; else stored as
    standalone entry for later linking."""

    _name = "kob.timer.entry"
    _description = "KOB Timesheet Timer Entry"
    _order = "stop_time desc"

    user_id = fields.Many2one(
        "res.users",
        default=lambda s: s.env.user,
        required=True,
        index=True,
    )
    description = fields.Char(required=True)
    start_time = fields.Datetime(required=True)
    stop_time = fields.Datetime()
    duration_seconds = fields.Integer(compute="_compute_duration", store=True)
    project_id = fields.Many2one("project.project")
    task_id = fields.Many2one("project.task")
    analytic_line_id = fields.Many2one(
        "account.analytic.line",
        readonly=True,
        help="Posted timesheet line — set after stop+commit",
    )

    @api.depends("start_time", "stop_time")
    def _compute_duration(self):
        for r in self:
            if r.start_time and r.stop_time:
                delta = r.stop_time - r.start_time
                r.duration_seconds = int(delta.total_seconds())
            else:
                r.duration_seconds = 0

    @api.model
    def commit_entry(self, payload):
        """Called from OWL component when user stops the timer.
        payload = {description, start_time, stop_time, project_id, task_id}
        Creates kob.timer.entry, optionally posts to account.analytic.line.
        """
        entry = self.create({
            "description": payload["description"] or "Untracked",
            "start_time": payload["start_time"],
            "stop_time": payload["stop_time"],
            "project_id": payload.get("project_id") or False,
            "task_id": payload.get("task_id") or False,
        })
        # If project + hr_timesheet present, also create analytic line
        if entry.project_id and entry.duration_seconds > 0:
            hours = round(entry.duration_seconds / 3600.0, 2)
            line = self.env["account.analytic.line"].create({
                "name": entry.description,
                "user_id": entry.user_id.id,
                "date": entry.stop_time.date(),
                "unit_amount": hours,
                "project_id": entry.project_id.id,
                "task_id": entry.task_id.id if entry.task_id else False,
                "account_id": entry.project_id.account_id.id if entry.project_id.account_id else False,
            })
            entry.analytic_line_id = line.id
        return {"id": entry.id, "duration_seconds": entry.duration_seconds}
