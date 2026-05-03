# -*- coding: utf-8 -*-
"""🔥 My Battle Board — Personal task inbox aggregator.

Single entry point: `kob.my.task.get_inbox(user_id=None)` returns
all pending tasks across modules that are assigned (directly or via
approval matrix / substitution) to the user, filtered by their role.
"""
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _


PRIORITY_WEIGHT = {"urgent": 100, "high": 75, "medium": 50, "low": 25}


def _to_date(v):
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    return None


def _flag_due(item):
    """Compute due_today / overdue flags from item['due_date']."""
    today = date.today()
    d = _to_date(item.get("due_date"))
    if d:
        item["due_today"] = (d == today)
        item["overdue"] = (d < today)
    else:
        item["due_today"] = False
        item["overdue"] = False
    return item


class KobMyTask(models.AbstractModel):
    _name = "kob.my.task"
    _description = "My Battle Board — Personal Task Inbox"

    # ════════════════════════════════════════════════════════════════════
    # Public API
    # ════════════════════════════════════════════════════════════════════

    @api.model
    def get_inbox(self, user_id=None):
        user = (self.env["res.users"].browse(user_id)
                if user_id else self.env.user)
        keys = self.env["kob.my.task.role.source.map"].keys_for_user(user)
        # Always allow activities (everyone has them)
        keys.add("activities")

        items = []
        # Personal tasks always included
        items += self._collect_personal(user)
        if "helpdesk"    in keys: items += self._collect_helpdesk(user)
        if "approval"    in keys: items += self._collect_approval_steps(user)
        if "field_svc"   in keys: items += self._collect_field_service(user)
        if "wms_count"   in keys: items += self._collect_count_tasks(user)
        if "kpi"         in keys: items += self._collect_kpi_assessments(user)
        if "returns"     in keys: items += self._collect_returns(user)
        if "ocr_review"  in keys: items += self._collect_ocr_review(user)
        if "activities"  in keys: items += self._collect_activities(user)
        if "ai"          in keys: items += self._collect_ai_suggestions(user)

        for it in items:
            _flag_due(it)
            it["priority_weight"] = PRIORITY_WEIGHT.get(
                it.get("priority", "medium"), 50)

        items.sort(key=lambda x: (
            not x.get("overdue", False),
            -x.get("priority_weight", 0),
            x.get("due_date") or "9999-12-31",
        ))

        return {
            "user_name":  user.name,
            "user_role":  self._user_role_label(user),
            "user_login": user.login,
            "kpi": {
                "total":     len(items),
                "overdue":   sum(1 for i in items if i.get("overdue")),
                "due_today": sum(1 for i in items if i.get("due_today")),
                "high_pri":  sum(1 for i in items
                                 if i.get("priority") in ("urgent", "high")),
            },
            "categories": self._category_counts(items),
            "items": items,
        }

    # ════════════════════════════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════════════════════════════
    @api.model
    def _user_role_label(self, user):
        WmsUser = self.env.get("kob.wms.user")
        if WmsUser is not None:
            ku = WmsUser.search([("res_user_id", "=", user.id)], limit=1)
            if ku and ku.role:
                return ku.role.replace("_", " ").title()
        # Fallback: highest WMS group
        for grp_xml, label in [
            ("kob_wms.group_wms_director",   "Director"),
            ("kob_wms.group_wms_manager",    "Manager"),
            ("kob_wms.group_wms_supervisor", "Supervisor"),
            ("kob_wms.group_wms_worker",     "Worker"),
        ]:
            grp = self.env.ref(grp_xml, raise_if_not_found=False)
            if grp and grp in user.groups_id:
                return label
        return "User"

    @api.model
    def _category_counts(self, items):
        out = {}
        for it in items:
            c = it.get("category", "other")
            out[c] = out.get(c, 0) + 1
        return out

    @api.model
    def _safe_iso(self, v):
        if not v:
            return None
        try:
            return v.isoformat() if hasattr(v, "isoformat") else str(v)
        except Exception:
            return None

    # ════════════════════════════════════════════════════════════════════
    # Collectors — each returns a list of unified item dicts
    # ════════════════════════════════════════════════════════════════════

    def _collect_personal(self, user):
        Task = self.env.get("kob.my.task.personal")
        if Task is None:
            return []
        # Owned by user OR assigned to user
        domain = [
            "|", "|",
            ("user_id", "=", user.id),
            ("assignee_ids", "in", [user.id]),
            ("watcher_ids", "in", [user.id]),
        ]
        domain.append(("state", "not in", ("done", "cancelled")))
        tasks = Task.sudo().search(domain, limit=100)
        cat_label = _("My Tasks")
        pri_map = {"0": "low", "1": "medium", "2": "high", "3": "urgent"}
        out = []
        for t in tasks:
            sub = ""
            if t.parent_id:
                sub = f"↳ subtask of {t.parent_id.name}"
            elif t.child_count:
                sub = f"{t.child_done_count}/{t.child_count} sub-tasks"
            if t.timer_running:
                sub = "⏱ running · " + (sub or "")
            out.append({
                "key":       f"{t._name}-{t.id}",
                "model":     t._name,
                "res_id":    t.id,
                "title":     t.name,
                "subtitle":  sub or (
                    ", ".join(t.tag_ids.mapped("name"))[:60]),
                "category":  "personal",
                "category_label": cat_label,
                "icon":      "🎯",
                "color":     "#ea580c",
                "state":     t.state,
                "state_label": dict(t._fields["state"]._description_selection(
                    self.env)).get(t.state, t.state),
                "priority":  pri_map.get(t.priority, "medium"),
                "due_date":  self._safe_iso(t.due_date),
            })
        return out

    def _collect_helpdesk(self, user):
        Ticket = self.env.get("kob.helpdesk.ticket")
        if Ticket is None:
            return []
        tickets = Ticket.sudo().search([
            ("assignee_id", "=", user.id),
            ("state", "in", ("new", "in_progress", "waiting")),
        ], limit=50)
        cat_label = _("Helpdesk")
        out = []
        for t in tickets:
            pri_map = {"0": "low", "1": "medium", "2": "high", "3": "urgent"}
            out.append({
                "key":       f"{t._name}-{t.id}",
                "model":     t._name,
                "res_id":    t.id,
                "title":     t.name or "(no subject)",
                "subtitle":  (t.category_id.name if t.category_id else "") +
                             (f" · {t.partner_id.name}" if t.partner_id else ""),
                "category":  "helpdesk",
                "category_label": cat_label,
                "icon":      "🎫",
                "color":     "#0a6ed1",
                "state":     t.state,
                "state_label": dict(t._fields["state"]._description_selection(
                    self.env)).get(t.state, t.state),
                "priority":  pri_map.get(getattr(t, "priority", "1"), "medium"),
                "due_date":  self._safe_iso(t.date_open),
                "created":   self._safe_iso(t.create_date),
            })
        return out

    def _collect_approval_steps(self, user):
        Step = self.env.get("kob.approval.step")
        if Step is None:
            return []
        # Direct: steps where approver_id == user
        domain = [("state", "=", "pending"),
                  ("approver_id", "=", user.id)]
        steps = Step.sudo().search(domain, limit=50)

        # Substitution: steps assigned to others where I'm their substitute
        Sub = self.env.get("kob.approval.substitution")
        if Sub is not None and hasattr(Sub, "resolve_approver"):
            today = date.today()
            other_steps = Step.sudo().search([
                ("state", "=", "pending"),
                ("approver_id", "!=", user.id),
            ], limit=200)
            for s in other_steps:
                try:
                    resolved = Sub.resolve_approver(
                        s.approver_id, today, None)
                    if resolved and resolved == user:
                        steps |= s
                except Exception:
                    pass

        out = []
        cat_label = _("Approvals")
        for s in steps:
            req = s.request_id
            amt = req.amount if req else 0
            out.append({
                "key":       f"{s._name}-{s.id}",
                "model":     "kob.approval.request",
                "res_id":    req.id if req else 0,
                "title":     req.name if req else f"Step {s.sequence}",
                "subtitle":  f"Step {s.sequence} · {req.request_type if req else ''}"
                             + (f" · {amt:,.0f}฿" if amt else ""),
                "category":  "approval",
                "category_label": cat_label,
                "icon":      "✅",
                "color":     "#107e3e",
                "state":     "pending",
                "state_label": "Pending Approval",
                "priority":  "high" if amt and amt > 1000000 else "medium",
                "due_date":  self._safe_iso(s.create_date),
                "amount":    amt,
            })
        return out

    def _collect_field_service(self, user):
        Task = self.env.get("kob.field.service.task")
        if Task is None:
            return []
        tasks = Task.sudo().search([
            ("technician_id", "=", user.id),
            ("state", "in", ("draft", "scheduled", "in_progress")),
        ], limit=50)
        cat_label = _("Field Service")
        out = []
        for t in tasks:
            out.append({
                "key":       f"{t._name}-{t.id}",
                "model":     t._name,
                "res_id":    t.id,
                "title":     t.name,
                "subtitle":  self._safe_iso(getattr(t, "schedule_date", None))
                             or "",
                "category":  "field_svc",
                "category_label": cat_label,
                "icon":      "🔧",
                "color":     "#a855f7",
                "state":     t.state,
                "state_label": t.state.replace("_", " ").title(),
                "priority":  "medium",
                "due_date":  self._safe_iso(getattr(t, "schedule_date", None)),
            })
        return out

    def _collect_count_tasks(self, user):
        Task = self.env.get("wms.count.task")
        if Task is None:
            return []
        tasks = Task.sudo().search([
            "|",
            ("assigned_user_id", "=", user.id),
            ("assigned_user_id", "=", False),
            ("state", "in", ("assigned", "counting")),
        ], limit=50)
        cat_label = _("WMS Count")
        out = []
        for t in tasks:
            loc = getattr(t.location_id, "complete_name", "") or t.location_id.name or ""
            out.append({
                "key":       f"{t._name}-{t.id}",
                "model":     t._name,
                "res_id":    t.id,
                "title":     t.name or t.abc_label or f"Task {t.id}",
                "subtitle":  (t.abc_label + " · " if t.abc_label else "") + loc,
                "category":  "wms_count",
                "category_label": cat_label,
                "icon":      "📦",
                "color":     "#354a5f",
                "state":     t.state,
                "state_label": t.state.title(),
                "priority":  "medium",
                "due_date":  self._safe_iso(t.create_date),
            })
        return out

    def _collect_kpi_assessments(self, user):
        Asm = self.env.get("wms.kpi.assessment")
        if Asm is None:
            return []
        # Assessments where this user is current approver or is the subject
        domain = ["|", "|", "|", "|",
                  ("user_id", "=", user.id),
                  ("supervisor_id", "=", user.id),
                  ("asst_manager_id", "=", user.id),
                  ("manager_id", "=", user.id),
                  ("director_id", "=", user.id)]
        asms = Asm.sudo().search(domain + [
            ("state", "not in", ("done", "rejected"))
        ], limit=50)
        cat_label = _("KPI")
        out = []
        for a in asms:
            out.append({
                "key":       f"{a._name}-{a.id}",
                "model":     a._name,
                "res_id":    a.id,
                "title":     a.display_name or f"KPI Assessment {a.id}",
                "subtitle":  f"State: {a.state}",
                "category":  "kpi",
                "category_label": cat_label,
                "icon":      "🎯",
                "color":     "#bb0000",
                "state":     a.state,
                "state_label": a.state.replace("_", " ").title(),
                "priority":  "high",
                "due_date":  self._safe_iso(a.create_date),
            })
        return out

    def _collect_returns(self, user):
        Ret = self.env.get("kob.return.request")
        if Ret is None:
            return []
        # No assigned_user — show submitted/approved that need action
        rmas = Ret.sudo().search([
            ("state", "in", ("submitted", "approved", "received", "inspected")),
        ], limit=30)
        cat_label = _("RMA")
        out = []
        for r in rmas:
            out.append({
                "key":       f"{r._name}-{r.id}",
                "model":     r._name,
                "res_id":    r.id,
                "title":     r.name,
                "subtitle":  (r.partner_id.name if r.partner_id else "") +
                             (f" · {r.reason_code}" if r.reason_code else ""),
                "category":  "returns",
                "category_label": cat_label,
                "icon":      "↩",
                "color":     "#06b6d4",
                "state":     r.state,
                "state_label": r.state.replace("_", " ").title(),
                "priority":  "medium",
                "due_date":  self._safe_iso(r.create_date),
            })
        return out

    def _collect_ocr_review(self, user):
        Q = self.env.get("kob.invoice.ocr.queue")
        if Q is None:
            return []
        items = Q.sudo().search([("state", "in", ("review", "failed"))], limit=30)
        cat_label = _("Invoice OCR")
        out = []
        for q in items:
            out.append({
                "key":       f"{q._name}-{q.id}",
                "model":     q._name,
                "res_id":    q.id,
                "title":     q.name,
                "subtitle":  (q.extracted_partner_name or "") +
                             (f" · ฿{q.extracted_amount:,.0f}"
                              if q.extracted_amount else ""),
                "category":  "ocr_review",
                "category_label": cat_label,
                "icon":      "🧾",
                "color":     "#f59e0b",
                "state":     q.state,
                "state_label": q.state.title(),
                "priority":  "medium",
                "due_date":  self._safe_iso(q.create_date),
            })
        return out

    def _collect_activities(self, user):
        Act = self.env["mail.activity"]
        acts = Act.sudo().search([("user_id", "=", user.id)], limit=50)
        cat_label = _("Activities")
        out = []
        for a in acts:
            try:
                source = self.env[a.res_model].sudo().browse(a.res_id)
                title = a.summary or (a.activity_type_id.name if a.activity_type_id else "Activity")
                subtitle = source.display_name if source.exists() else a.res_model
            except Exception:
                title = a.summary or "Activity"
                subtitle = a.res_model
            today = date.today()
            d = a.date_deadline
            pri = ("urgent" if d and d < today else
                   "high" if d and d == today else "medium")
            out.append({
                "key":       f"{a._name}-{a.id}",
                "model":     a.res_model,
                "res_id":    a.res_id,
                "title":     title,
                "subtitle":  subtitle,
                "category":  "activities",
                "category_label": cat_label,
                "icon":      "📝",
                "color":     "#5d9ff5",
                "state":     "pending",
                "state_label": "Pending",
                "priority":  pri,
                "due_date":  self._safe_iso(a.date_deadline),
            })
        return out

    def _collect_ai_suggestions(self, user):
        Sug = self.env.get("kob.ai.suggestion")
        if Sug is None:
            return []
        items = Sug.sudo().search([
            ("state", "=", "new"),
            ("priority", "in", ("2", "3")),  # high + critical only
        ], limit=20)
        cat_label = _("AI Suggestion")
        out = []
        for s in items:
            pri_map = {"0": "low", "1": "medium", "2": "high", "3": "urgent"}
            out.append({
                "key":       f"{s._name}-{s.id}",
                "model":     s._name,
                "res_id":    s.id,
                "title":     s.title,
                "subtitle":  (s.message or "")[:100],
                "category":  "ai",
                "category_label": cat_label,
                "icon":      "✨",
                "color":     "#ec4899",
                "state":     s.state,
                "state_label": s.state.title(),
                "priority":  pri_map.get(s.priority, "medium"),
                "due_date":  self._safe_iso(s.create_date),
            })
        return out
