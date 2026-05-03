from odoo import api, fields, models


class StageTransition(models.Model):
    _name = "kob.stage.transition"
    _description = "Stage transition audit log (polymorphic)"
    _order = "transitioned_at desc, id desc"
    _rec_name = "display_name"

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    res_name = fields.Char(compute="_compute_res_name", store=True)

    stage_from = fields.Char()
    stage_to = fields.Char()
    transitioned_at = fields.Datetime(
        required=True, default=fields.Datetime.now, index=True,
    )
    transitioned_by = fields.Many2one("res.users")
    duration_in_previous_min = fields.Integer(
        help="Working minutes spent in stage_from before this transition.",
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        for r in self:
            r.res_name = ""
            if not r.res_model or not r.res_id:
                continue
            Model = self.env.get(r.res_model)
            if Model is None:
                continue
            rec = Model.browse(r.res_id).exists()
            if rec:
                r.res_name = rec.display_name

    @api.depends("res_model", "res_id", "stage_from", "stage_to", "res_name")
    def _compute_display_name(self):
        for r in self:
            arrow = " → ".join([s for s in [r.stage_from or "(new)", r.stage_to or ""] if s])
            r.display_name = f"{r.res_name or r.res_model}/{r.res_id}: {arrow}"

    def action_open_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def get_history_for(self, res_model, res_id):
        """Return ordered transition history for a single record."""
        return self.search([
            ("res_model", "=", res_model),
            ("res_id", "=", res_id),
        ], order="transitioned_at asc, id asc")

    def upstream_chain(self, res_model, res_id):
        """Walk known link patterns backward to upstream records.

        Returns list of dicts: [{model, id, name, transitions: [...]}, ...]
        ordered from current record to ultimate origin.
        """
        chain = []
        seen = set()
        cur_model, cur_id = res_model, res_id
        while cur_model and cur_id and (cur_model, cur_id) not in seen:
            seen.add((cur_model, cur_id))
            Model = self.env.get(cur_model)
            if Model is None:
                break
            rec = Model.browse(cur_id).exists()
            if not rec:
                break
            transitions = self.get_history_for(cur_model, cur_id)
            chain.append({
                "model": cur_model,
                "id": cur_id,
                "name": rec.display_name,
                "transitions": [{
                    "from": t.stage_from,
                    "to": t.stage_to,
                    "at": fields.Datetime.to_string(t.transitioned_at),
                    "duration_min": t.duration_in_previous_min,
                } for t in transitions],
            })
            cur_model, cur_id = self._next_upstream(rec)
        return chain

    def _next_upstream(self, rec):
        """Walk upstream by known link fields. Returns (model, id) or (None, None)."""
        # stock.picking → purchase.order via origin (po name)
        if rec._name == "stock.picking" and rec.origin:
            PO = self.env.get("purchase.order")
            if PO is not None:
                po = PO.search([("name", "=", rec.origin)], limit=1)
                if po:
                    return ("purchase.order", po.id)
        # purchase.order → kob.approval.request via origin or any custom field
        if rec._name == "purchase.order":
            ApprovalReq = self.env.get("kob.approval.request")
            if ApprovalReq is not None and "approval_request_id" in rec._fields and rec.approval_request_id:
                return ("kob.approval.request", rec.approval_request_id.id)
        # kob.approval.request → kob.approval.step is downstream actually; chain stops here
        # stock.picking → mrp.production via origin
        if rec._name == "stock.picking" and rec.origin and "mrp.production" in self.env:
            MO = self.env["mrp.production"]
            mo = MO.search([("name", "=", rec.origin)], limit=1)
            if mo:
                return ("mrp.production", mo.id)
        return (None, None)
