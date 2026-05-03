# -*- coding: utf-8 -*-
"""🔥 My Battle Board — Personal Task Manager.

Full task manager with:
  - Sub-tasks & dependencies (parent/child + blocking)
  - Collaboration (mail.thread + assignees + watchers)
  - Time tracking (start/stop timer + duration log)
  - Automation (rules engine, triggered on state change)
  - Reporting (daily/weekly digest cron)
  - Integration (link to any res_model+res_id)
  - Quick-create
"""
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobMyTaskPersonal(models.Model):
    _name = "kob.my.task.personal"
    _description = "My Battle Board — Personal Task"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, due_date, id desc"

    name = fields.Char(string="Task", required=True, tracking=True)
    description = fields.Html(sanitize=True)
    user_id = fields.Many2one(
        "res.users", string="Owner", required=True,
        default=lambda s: s.env.user, tracking=True, index=True,
    )
    assignee_ids = fields.Many2many(
        "res.users", "kob_my_task_assignees_rel",
        "task_id", "user_id", string="Collaborators")
    watcher_ids = fields.Many2many(
        "res.users", "kob_my_task_watchers_rel",
        "task_id", "user_id", string="Watchers")

    # ── Hierarchy + Dependencies ──────────────────────────────────────
    parent_id = fields.Many2one(
        "kob.my.task.personal", string="Parent Task",
        ondelete="cascade", index=True)
    child_ids = fields.One2many(
        "kob.my.task.personal", "parent_id", string="Sub-tasks")
    child_count = fields.Integer(compute="_compute_child_count")
    child_done_count = fields.Integer(compute="_compute_child_count")
    child_progress = fields.Float(
        string="Sub-task Progress %", compute="_compute_child_count")

    blocked_by_ids = fields.Many2many(
        "kob.my.task.personal", "kob_my_task_dep_rel",
        "task_id", "blocker_id", string="Blocked by",
        help="This task can't start until these are done.")
    blocking_ids = fields.Many2many(
        "kob.my.task.personal", "kob_my_task_dep_rel",
        "blocker_id", "task_id", string="Blocking")
    is_blocked = fields.Boolean(compute="_compute_is_blocked", store=False)

    # ── State + priority ──────────────────────────────────────────────
    state = fields.Selection(
        [("todo", "📋 To Do"),
         ("in_progress", "🔥 In Progress"),
         ("blocked", "⛔ Blocked"),
         ("review", "👁 Review"),
         ("done", "✅ Done"),
         ("cancelled", "❌ Cancelled")],
        default="todo", required=True, tracking=True, index=True,
    )
    priority = fields.Selection(
        [("0", "Low"), ("1", "Medium"), ("2", "High"), ("3", "🔥 Urgent")],
        default="1", required=True, tracking=True,
    )
    tag_ids = fields.Many2many("kob.my.task.tag", string="Tags")

    # ── Dates ────────────────────────────────────────────────────────
    due_date = fields.Date(tracking=True)
    start_date = fields.Date()
    completed_date = fields.Datetime(readonly=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", store=False)
    is_due_today = fields.Boolean(compute="_compute_is_overdue", store=False)

    # ── Time tracking ────────────────────────────────────────────────
    estimated_hours = fields.Float(string="Estimated Hours")
    spent_hours = fields.Float(
        string="Spent Hours", compute="_compute_spent_hours", store=True)
    timer_running = fields.Boolean(default=False, readonly=True)
    timer_started_at = fields.Datetime(readonly=True)
    timer_log_ids = fields.One2many(
        "kob.my.task.time.log", "task_id", string="Time Logs")
    progress_pct = fields.Float(compute="_compute_progress_pct")

    # ── Integration: link to source record ────────────────────────────
    linked_model = fields.Char(string="Linked Model")
    linked_id = fields.Integer(string="Linked Record")
    linked_label = fields.Char(string="Linked Label")

    # ── Visibility ───────────────────────────────────────────────────
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)
    color = fields.Integer()
    active = fields.Boolean(default=True)

    # ──────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────
    @api.depends("child_ids.state")
    def _compute_child_count(self):
        for r in self:
            children = r.child_ids
            done = children.filtered(lambda c: c.state == "done")
            r.child_count = len(children)
            r.child_done_count = len(done)
            r.child_progress = (
                100.0 * len(done) / len(children) if children else 0)

    @api.depends("blocked_by_ids", "blocked_by_ids.state")
    def _compute_is_blocked(self):
        for r in self:
            r.is_blocked = any(b.state not in ("done", "cancelled")
                               for b in r.blocked_by_ids)

    def _compute_is_overdue(self):
        today = date.today()
        for r in self:
            r.is_overdue = (
                r.due_date and r.due_date < today
                and r.state not in ("done", "cancelled"))
            r.is_due_today = (r.due_date == today
                              and r.state not in ("done", "cancelled"))

    @api.depends("timer_log_ids.duration_hours", "timer_running",
                 "timer_started_at")
    def _compute_spent_hours(self):
        for r in self:
            total = sum(r.timer_log_ids.mapped("duration_hours"))
            if r.timer_running and r.timer_started_at:
                delta = (datetime.now() - r.timer_started_at).total_seconds()
                total += delta / 3600.0
            r.spent_hours = round(total, 2)

    @api.depends("estimated_hours", "spent_hours", "child_progress",
                 "state")
    def _compute_progress_pct(self):
        for r in self:
            if r.state == "done":
                r.progress_pct = 100
            elif r.state == "cancelled":
                r.progress_pct = 0
            elif r.child_count > 0:
                r.progress_pct = r.child_progress
            elif r.estimated_hours and r.spent_hours:
                r.progress_pct = min(100,
                                     r.spent_hours / r.estimated_hours * 100)
            else:
                r.progress_pct = 50 if r.state == "in_progress" else 0

    # ──────────────────────────────────────────────────────────────────
    # State transitions
    # ──────────────────────────────────────────────────────────────────
    def action_start(self):
        for r in self:
            if r.is_blocked:
                raise UserError(_(
                    "Cannot start: blocked by %s") %
                    ", ".join(r.blocked_by_ids.mapped("name")))
            r.state = "in_progress"

    def action_done(self):
        for r in self:
            if r.timer_running:
                r.action_stop_timer()
            r.write({"state": "done", "completed_date": fields.Datetime.now()})
            # Trigger automation rules
            self.env["kob.my.task.rule"].run_for_event("on_done", r)

    def action_block(self):
        self.write({"state": "blocked"})

    def action_review(self):
        self.write({"state": "review"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_to_todo(self):
        self.write({"state": "todo"})

    # ──────────────────────────────────────────────────────────────────
    # Time tracking
    # ──────────────────────────────────────────────────────────────────
    def action_start_timer(self):
        for r in self:
            if r.timer_running:
                continue
            r.write({
                "timer_running": True,
                "timer_started_at": fields.Datetime.now(),
            })
            if r.state == "todo":
                r.state = "in_progress"

    def action_stop_timer(self):
        Log = self.env["kob.my.task.time.log"]
        now = fields.Datetime.now()
        for r in self:
            if not r.timer_running or not r.timer_started_at:
                continue
            secs = (now - r.timer_started_at).total_seconds()
            Log.create({
                "task_id": r.id,
                "user_id": self.env.user.id,
                "started_at": r.timer_started_at,
                "ended_at": now,
                "duration_hours": round(secs / 3600.0, 4),
            })
            r.write({"timer_running": False, "timer_started_at": False})

    # ──────────────────────────────────────────────────────────────────
    # Quick create (used by OWL inline composer)
    # ──────────────────────────────────────────────────────────────────
    @api.model
    def quick_create(self, name, due_date=None, priority="1",
                     parent_id=None, linked_model=None, linked_id=None):
        vals = {"name": name, "priority": priority}
        if due_date: vals["due_date"] = due_date
        if parent_id: vals["parent_id"] = parent_id
        if linked_model and linked_id:
            vals["linked_model"] = linked_model
            vals["linked_id"] = linked_id
        rec = self.create(vals)
        return {
            "id": rec.id,
            "name": rec.name,
            "state": rec.state,
            "due_date": rec.due_date and rec.due_date.isoformat(),
        }


class KobMyTaskTag(models.Model):
    _name = "kob.my.task.tag"
    _description = "My Task Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer()


class KobMyTaskTimeLog(models.Model):
    _name = "kob.my.task.time.log"
    _description = "Time Log"
    _order = "started_at desc"

    task_id = fields.Many2one(
        "kob.my.task.personal", required=True, ondelete="cascade")
    user_id = fields.Many2one(
        "res.users", required=True, default=lambda s: s.env.user)
    started_at = fields.Datetime(required=True)
    ended_at = fields.Datetime(required=True)
    duration_hours = fields.Float(required=True)
    note = fields.Char()


class KobMyTaskRule(models.Model):
    """Automation rule — triggers actions on state change events."""
    _name = "kob.my.task.rule"
    _description = "My Task Automation Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    trigger_event = fields.Selection(
        [("on_done", "When task marked Done"),
         ("on_overdue", "When task becomes Overdue"),
         ("on_blocked", "When task gets Blocked"),
         ("on_high_pri_create", "When High/Urgent task created")],
        required=True, default="on_done",
    )
    condition_state = fields.Char(
        help="Optional Python expr evaluated against `task` "
             "(e.g. 'task.priority == \"3\"')")
    action_type = fields.Selection(
        [("notify_user", "Notify Owner"),
         ("notify_watchers", "Notify Watchers"),
         ("create_subtask", "Auto-create follow-up sub-task"),
         ("set_priority", "Bump priority")],
        required=True, default="notify_user",
    )
    notify_message = fields.Text(default="Task '{name}' triggered rule.")
    follow_up_template = fields.Char(default="Follow up: {name}")
    bump_priority = fields.Selection(
        [("1", "Medium"), ("2", "High"), ("3", "Urgent")], default="2")

    @api.model
    def run_for_event(self, event, task):
        rules = self.search([
            ("active", "=", True),
            ("trigger_event", "=", event),
        ])
        for r in rules:
            try:
                if r.condition_state:
                    if not eval(r.condition_state, {"task": task}):  # nosec
                        continue
                r._do_action(task)
            except Exception:
                pass

    def _do_action(self, task):
        if self.action_type == "notify_user":
            task.message_post(
                body=(self.notify_message or "Rule {}").format(name=task.name),
                partner_ids=[task.user_id.partner_id.id])
        elif self.action_type == "notify_watchers":
            task.message_post(
                body=(self.notify_message or "Rule {}").format(name=task.name),
                partner_ids=task.watcher_ids.mapped("partner_id.id"))
        elif self.action_type == "create_subtask":
            self.env["kob.my.task.personal"].create({
                "name": (self.follow_up_template or
                         "Follow up: {name}").format(name=task.name),
                "parent_id": task.id,
                "user_id": task.user_id.id,
                "priority": task.priority,
            })
        elif self.action_type == "set_priority":
            task.priority = self.bump_priority


class KobMyTaskDigest(models.AbstractModel):
    """Daily / Weekly digest cron — sends a summary email per user."""
    _name = "kob.my.task.digest"
    _description = "My Task Digest"

    @api.model
    def cron_send_daily_digest(self):
        return self._send_digest("daily")

    @api.model
    def cron_send_weekly_digest(self):
        return self._send_digest("weekly")

    @api.model
    def _send_digest(self, kind):
        Task = self.env["kob.my.task.personal"]
        Mail = self.env["mail.mail"].sudo()
        today = date.today()
        week_ago = today - timedelta(days=7)

        users = Task.read_group(
            [("state", "not in", ("done", "cancelled"))],
            ["user_id"], ["user_id"])
        sent = 0
        for grp in users:
            uid = grp["user_id"][0] if grp["user_id"] else False
            if not uid:
                continue
            user = self.env["res.users"].browse(uid)
            if not user.email:
                continue

            open_tasks = Task.search([
                ("user_id", "=", uid),
                ("state", "not in", ("done", "cancelled")),
            ])
            overdue = open_tasks.filtered(lambda t: t.is_overdue)
            today_tasks = open_tasks.filtered(lambda t: t.is_due_today)
            done_recent = Task.search([
                ("user_id", "=", uid),
                ("state", "=", "done"),
                ("completed_date", ">=", week_ago if kind == "weekly" else today),
            ])

            html = self._render_html(
                kind, user, open_tasks, overdue, today_tasks, done_recent)
            subject = (f"🔥 My Battle Board — "
                       f"{'รายงานประจำวัน' if kind == 'daily' else 'รายงานสัปดาห์'} "
                       f"({today.isoformat()})")
            Mail.create({
                "subject": subject,
                "email_from": "no-reply@kob.local",
                "email_to": user.email,
                "body_html": html,
            }).send()
            sent += 1
        return sent

    def _render_html(self, kind, user, open_tasks, overdue, today, done_recent):
        rows = []
        for t in (overdue | today | open_tasks)[:20]:
            tag = "⚠ OVERDUE" if t.is_overdue else (
                  "⏰ TODAY" if t.is_due_today else "")
            rows.append(
                f"<tr><td>{t.name}</td><td>{t.state}</td>"
                f"<td>{t.due_date or ''}</td><td>{tag}</td></tr>")
        done_rows = "".join(
            f"<li>{t.name}</li>" for t in done_recent[:20]) or "<li>—</li>"
        return f"""
<h2>🔥 My Battle Board — {'Daily' if kind == 'daily' else 'Weekly'} Digest</h2>
<p>สวัสดี {user.name}, นี่คือสรุปงานของคุณ:</p>
<ul>
  <li><strong>Open</strong>: {len(open_tasks)}</li>
  <li><strong>Overdue</strong>: {len(overdue)} ⚠</li>
  <li><strong>Due today</strong>: {len(today)} ⏰</li>
  <li><strong>Completed</strong>: {len(done_recent)} ✅</li>
</ul>
<h3>Open Tasks</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
<tr><th>Name</th><th>State</th><th>Due</th><th>Tag</th></tr>
{''.join(rows) or '<tr><td colspan="4">No open tasks</td></tr>'}
</table>
<h3>Recently Completed</h3>
<ul>{done_rows}</ul>
<p><em>เปิด My Battle Board เพื่อดูรายละเอียดและจัดการงานต่อ</em></p>
"""
