"""Agentic AI runner — executes LLM with tool-use, posts suggestions
that need human approval before any actual write."""

import json
import logging
import os

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KobAiAgentRun(models.Model):
    _name = "kob.ai.agent.run"
    _description = "KOB AI Agent Execution"
    _order = "create_date desc"

    name = fields.Char(default="Agent run", required=True)
    model = fields.Char(
        default=lambda s: os.environ.get("KOB_AI_MODEL", "claude-sonnet-4-6"),
        help="LLM model id (Anthropic or OpenAI)",
    )
    trigger = fields.Selection(
        [("manual", "Manual"), ("cron", "Cron"), ("api", "API")],
        default="manual",
    )
    prompt = fields.Text(required=True)
    output = fields.Text(readonly=True)
    tool_call_count = fields.Integer(readonly=True)
    suggestion_count = fields.Integer(readonly=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("error", "Error"),
            ("blocked", "Blocked (no API key)"),
        ],
        default="pending",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    cost_estimate = fields.Float(
        digits=(10, 4),
        readonly=True,
        help="Estimated USD cost (input+output tokens × pricing)",
    )
    duration_seconds = fields.Float(readonly=True)
    user_id = fields.Many2one(
        "res.users",
        default=lambda s: s.env.user,
        required=True,
    )
    suggestion_count_field = fields.Integer(compute="_compute_suggestion_count")

    @api.depends()
    def _compute_suggestion_count(self):
        Suggestion = self.env.get("kob.ai.suggestion")
        for r in self:
            r.suggestion_count_field = Suggestion.search_count([("run_id", "=", r.id)]) if Suggestion is not None else 0

    def action_run(self):
        """Trigger LLM execution synchronously (max 60s)."""
        for r in self:
            r._execute()

    def _execute(self):
        import time
        self.ensure_one()
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.write({
                "status": "blocked",
                "error_message": "No ANTHROPIC_API_KEY / OPENAI_API_KEY env var set",
            })
            return
        self.write({"status": "running"})
        t0 = time.time()
        try:
            tools = self.env["kob.ai.tool"].search([("active", "=", True)])
            tool_specs = [t._tool_spec() for t in tools]
            response = self._call_llm(api_key, tool_specs)
            self.write({
                "output": response.get("text", ""),
                "tool_call_count": len(response.get("tool_calls", [])),
                "cost_estimate": response.get("cost", 0.0),
                "status": "done",
                "duration_seconds": time.time() - t0,
            })
            # Process tool_calls — each becomes a suggestion (NOT executed)
            for tc in response.get("tool_calls", []):
                self.env["kob.ai.suggestion"].create({
                    "run_id": self.id,
                    "tool_name": tc.get("name"),
                    "tool_args": json.dumps(tc.get("args", {}), ensure_ascii=False),
                    "rationale": tc.get("rationale", ""),
                    "status": "pending",
                })
            self.suggestion_count = len(self.suggestion_ids)
        except Exception as e:
            _logger.exception("AI agent run failed")
            self.write({
                "status": "error",
                "error_message": str(e)[:2000],
                "duration_seconds": time.time() - t0,
            })

    def _call_llm(self, api_key, tool_specs):
        """Stub. Real implementation imports anthropic / openai SDK and
        passes tools. For now returns a canned 'no API call' notice."""
        # Replace this with actual API call when SDK is installed.
        # import anthropic
        # client = anthropic.Anthropic(api_key=api_key)
        # message = client.messages.create(model=self.model, ...)
        return {
            "text": "[Stub] LLM client not wired. Configure anthropic SDK + "
                    "implement _call_llm to enable real agentic behavior.",
            "tool_calls": [],
            "cost": 0.0,
        }


# KobAiSuggestion model lives in suggestion.py (separate file)
