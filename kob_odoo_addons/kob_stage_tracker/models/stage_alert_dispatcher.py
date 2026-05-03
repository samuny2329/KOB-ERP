import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class StageAlertDispatcher(models.AbstractModel):
    _name = "kob.stage.alert.dispatcher"
    _description = "Cron + dispatch logic for stage threshold alerts"

    @api.model
    def cron_scan_breaches(self):
        Threshold = self.env["kob.stage.threshold"].sudo()
        thresholds = Threshold.search([("active", "=", True)])
        total = 0
        for th in thresholds:
            try:
                total += self._scan_threshold(th)
            except Exception as e:
                _logger.exception("Stage threshold scan failed: %s", th.name)
        return total

    def _scan_threshold(self, th):
        Model = self.env.get(th.res_model)
        if Model is None:
            return 0
        if "current_stage_started_at" not in Model._fields:
            return 0
        cutoff = fields.Datetime.now() - timedelta(minutes=th.threshold_minutes)
        state_field = th.state_field or "state"
        domain = [
            (state_field, "=", th.state_value),
            ("current_stage_started_at", "!=", False),
            ("current_stage_started_at", "<=", cutoff),
        ]
        breached = Model.search(domain)
        count = 0
        for rec in breached:
            if self._already_alerted(rec, th):
                continue
            try:
                self._dispatch_alert(rec, th)
                count += 1
            except Exception:
                _logger.exception("Alert dispatch failed for %s", rec)
        th.write({
            "last_scan_at": fields.Datetime.now(),
            "last_scan_breaches": count,
        })
        return count

    def _already_alerted(self, rec, th):
        """Skip if there's already an open mail.activity from us in last 24h."""
        if th.action_type != "activity":
            return False
        Activity = self.env["mail.activity"].sudo()
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        return bool(Activity.search_count([
            ("res_model", "=", rec._name),
            ("res_id", "=", rec.id),
            ("summary", "like", f"[StageBreach:{th.id}]%"),
            ("create_date", ">=", cutoff),
        ]))

    def _dispatch_alert(self, rec, th):
        if th.action_type == "activity":
            self._dispatch_activity(rec, th)
        elif th.action_type == "battle_board":
            self._dispatch_battle_board(rec, th)
        elif th.action_type == "discuss":
            self._dispatch_discuss(rec, th)
        elif th.action_type == "ai":
            self._dispatch_ai(rec, th)

    def _dispatch_activity(self, rec, th):
        user = self._resolve_user(rec, th)
        if not user:
            return
        elapsed = rec.total_active_stage_min if "total_active_stage_min" in rec._fields else 0
        Activity = self.env["mail.activity"].sudo()
        try:
            todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        except Exception:
            todo = None
        Activity.create({
            "res_model": rec._name,
            "res_model_id": self.env["ir.model"]._get(rec._name).id,
            "res_id": rec.id,
            "user_id": user.id,
            "summary": f"[StageBreach:{th.id}] Stage breach ({th.severity})",
            "note": (
                f"Record {rec.display_name} has been in stage "
                f"<b>{th.state_value}</b> for {elapsed} working minutes "
                f"(threshold {th.threshold_minutes} min)."
            ),
            "activity_type_id": todo.id if todo else False,
            "date_deadline": fields.Date.today(),
        })

    def _dispatch_battle_board(self, rec, th):
        Task = self.env.get("kob.my.task.personal")
        if Task is None:
            return self._dispatch_activity(rec, th)
        user = self._resolve_user(rec, th) or self.env.user
        elapsed = rec.total_active_stage_min if "total_active_stage_min" in rec._fields else 0
        Task.sudo().create({
            "name": f"⚠ Stage breach: {rec.display_name} stuck in {th.state_value}",
            "user_id": user.id,
            "priority": "1" if th.severity == "high" else "0",
            "description": (
                f"Held {elapsed} min (threshold {th.threshold_minutes}). "
                f"Source: {rec._name}/{rec.id}."
            ),
        })

    def _dispatch_discuss(self, rec, th):
        if not th.target_channel_id:
            return self._dispatch_activity(rec, th)
        elapsed = rec.total_active_stage_min if "total_active_stage_min" in rec._fields else 0
        th.target_channel_id.sudo().message_post(
            body=(
                f"🕐 Stage breach — <b>{rec.display_name}</b> "
                f"in <b>{th.state_value}</b> for {elapsed} min "
                f"(threshold {th.threshold_minutes})."
            ),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _dispatch_ai(self, rec, th):
        Run = self.env.get("kob.ai.agent.run")
        if Run is None:
            return self._dispatch_activity(rec, th)
        Run.sudo().create({
            "name": f"Stage breach: {rec._name}/{rec.id}",
            "trigger": "cron",
            "prompt": (
                f"Investigate stage breach: record {rec._name}/{rec.id} "
                f"({rec.display_name}) is stuck in stage '{th.state_value}'. "
                f"Suggest next action."
            ),
        })

    def _resolve_user(self, rec, th):
        field = th.target_user_field or "user_id"
        if field in rec._fields and rec[field]:
            return rec[field]
        if "create_uid" in rec._fields:
            return rec.create_uid
        return None
