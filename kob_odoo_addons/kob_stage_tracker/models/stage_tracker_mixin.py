from odoo import api, fields, models


class StageTrackerMixin(models.AbstractModel):
    _name = "kob.stage.tracker.mixin"
    _description = "Tracks stage transitions with timestamps + alerts"

    # Override on each implementing model
    _stage_field = "state"
    _stage_terminal = ()       # tuple of values meaning "done — stop alerting"
    _stage_track_on_create = True

    current_stage_started_at = fields.Datetime(
        readonly=True, copy=False, index=True,
    )
    total_active_stage_min = fields.Integer(
        compute="_compute_total_active_stage_min",
        help="Working minutes since current stage started.",
    )
    stage_breach_warning = fields.Selection(
        [("ok", "OK"), ("warning", "Warning"), ("breached", "Breached")],
        compute="_compute_stage_breach_warning",
    )

    def _compute_total_active_stage_min(self):
        for r in self:
            if not r.current_stage_started_at:
                r.total_active_stage_min = 0
                continue
            r.total_active_stage_min = r._net_minutes_between(
                r.current_stage_started_at, fields.Datetime.now(),
            )

    def _compute_stage_breach_warning(self):
        Threshold = self.env["kob.stage.threshold"].sudo()
        for r in self:
            current = r[r._stage_field] if r._stage_field in r._fields else False
            if not current or current in r._stage_terminal:
                r.stage_breach_warning = "ok"
                continue
            th = Threshold.search([
                ("res_model", "=", r._name),
                ("state_value", "=", str(current)),
                ("active", "=", True),
            ], limit=1)
            if not th or not r.current_stage_started_at:
                r.stage_breach_warning = "ok"
                continue
            elapsed = r.total_active_stage_min
            if elapsed >= th.threshold_minutes:
                r.stage_breach_warning = "breached"
            elif elapsed >= 0.8 * th.threshold_minutes:
                r.stage_breach_warning = "warning"
            else:
                r.stage_breach_warning = "ok"

    def write(self, vals):
        if self.env.context.get("kob_stage_skip_track"):
            return super().write(vals)
        stage_field = self._stage_field
        if stage_field and stage_field in vals:
            before = {r.id: r[stage_field] for r in self}
            res = super().write(vals)
            for r in self:
                new_val = r[stage_field]
                if before[r.id] != new_val:
                    r._record_stage_transition(before[r.id], new_val)
            return res
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self._stage_track_on_create:
            for r in recs:
                cur = r[r._stage_field] if r._stage_field in r._fields else False
                r._record_stage_transition(False, cur)
        return recs

    def _record_stage_transition(self, old_state, new_state):
        self.ensure_one()
        Transition = self.env["kob.stage.transition"].sudo()
        now = fields.Datetime.now()
        duration_min = 0
        if self.current_stage_started_at:
            duration_min = self._net_minutes_between(
                self.current_stage_started_at, now,
            )
        Transition.create({
            "res_model": self._name,
            "res_id": self.id,
            "stage_from": str(old_state) if old_state else False,
            "stage_to": str(new_state) if new_state else False,
            "transitioned_at": now,
            "transitioned_by": self.env.user.id,
            "duration_in_previous_min": duration_min,
        })
        self.with_context(kob_stage_skip_track=True).write({
            "current_stage_started_at": now,
        })

    def _net_minutes_between(self, start, end):
        """Wrap wms.sla.config.net_working_minutes if installed.
        Falls back to wall-clock minutes."""
        Sla = self.env.get("wms.sla.config")
        if Sla is not None:
            sla = Sla.search([("active", "=", True)], limit=1)
            if sla and hasattr(sla, "net_working_minutes"):
                try:
                    return sla.net_working_minutes(start, end)
                except Exception:
                    pass
        return int((end - start).total_seconds() / 60)

    def action_view_stage_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Stage history",
            "res_model": "kob.stage.transition",
            "view_mode": "list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def action_view_upstream_chain(self):
        self.ensure_one()
        chain = self.env["kob.stage.transition"].upstream_chain(self._name, self.id)
        # Collect every (model, id) from the chain → open transition list
        if not chain:
            return {"type": "ir.actions.act_window_close"}
        domain = ["|"] * (len(chain) - 1)
        for item in chain:
            domain.extend([
                "&",
                ("res_model", "=", item["model"]),
                ("res_id", "=", item["id"]),
            ])
        return {
            "type": "ir.actions.act_window",
            "name": "Upstream chain",
            "res_model": "kob.stage.transition",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_groupby_res_model": 1},
        }
