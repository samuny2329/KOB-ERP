"""kob.ai.suggestion — agent-proposed action awaiting human approval."""

import json

from odoo import api, fields, models, _


class KobAiSuggestion(models.Model):
    _name = "kob.ai.suggestion"
    _description = "KOB AI Suggestion (pending human approval)"
    _order = "priority desc, create_date desc"
    _inherit = ["mail.thread"]

    run_id = fields.Many2one(
        "kob.ai.agent.run",
        ondelete="cascade",
        required=True,
        index=True,
    )
    tool_name = fields.Char(required=True, tracking=True)
    tool_args = fields.Text(help="JSON-encoded args the agent wants to call with")
    rationale = fields.Text(help="Agent's stated reason for the suggestion")
    priority = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")],
        default="normal",
        tracking=True,
    )
    status = fields.Selection(
        [
            ("pending", "Pending review"),
            ("approved", "Approved & executed"),
            ("rejected", "Rejected"),
            ("error", "Execution error"),
        ],
        default="pending",
        tracking=True,
    )
    approver_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    execution_result = fields.Text(readonly=True)

    def action_approve(self):
        for s in self:
            if s.status != "pending":
                continue
            tool = self.env["kob.ai.tool"].search([("name", "=", s.tool_name)], limit=1)
            if not tool:
                s.write({
                    "status": "error",
                    "execution_result": "Tool not registered: %s" % s.tool_name,
                })
                continue
            try:
                args = json.loads(s.tool_args or "{}")
                result = tool.execute(args)
                s.write({
                    "status": "approved",
                    "approver_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "execution_result": json.dumps(result, default=str)[:5000],
                })
            except Exception as e:
                s.write({"status": "error", "execution_result": str(e)[:2000]})

    def action_reject(self):
        self.write({
            "status": "rejected",
            "approver_id": self.env.user.id,
        })
