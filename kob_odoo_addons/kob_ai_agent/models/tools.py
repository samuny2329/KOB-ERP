"""Whitelisted server-side tools the AI agent may call.

To register a new tool: create a record in data/tools.xml referencing
a Python method on this model (or any model). The agent receives a
JSON schema describing the tool and may emit a tool_call which becomes
a kob.ai.suggestion for human approval before execution.
"""

from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobAiTool(models.Model):
    _name = "kob.ai.tool"
    _description = "KOB AI Agent Tool (whitelisted)"
    _order = "name"

    name = fields.Char(required=True, help="Unique tool id (e.g. list_overdue_invoices)")
    description = fields.Text(
        required=True,
        help="What the tool does (shown to LLM to help it decide)",
    )
    args_schema = fields.Text(
        help="JSON schema describing args (subset of OpenAPI / Anthropic format)",
        default="{}",
    )
    method_model = fields.Char(
        required=True,
        help="Model where the implementation lives, e.g. kob.ai.tool",
    )
    method_name = fields.Char(
        required=True,
        help="Method name on the model (must accept dict 'args' and return JSON-able)",
    )
    active = fields.Boolean(default=True)
    require_role = fields.Many2one(
        "res.groups",
        help="If set, only users in this group can approve suggestions of this tool",
    )

    _sql_constraints = [
        ("name_unique", "unique(name)", "Tool name must be unique"),
    ]

    def _tool_spec(self):
        """Return JSON spec ready for Anthropic/OpenAI tool-use payload."""
        import json
        self.ensure_one()
        try:
            schema = json.loads(self.args_schema or "{}")
        except Exception:
            schema = {}
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
        }

    def execute(self, args):
        """Dispatch to backing model.method(args)."""
        self.ensure_one()
        model = self.env[self.method_model]
        if not hasattr(model, self.method_name):
            raise UserError(_("Method %s.%s not found") % (self.method_model, self.method_name))
        return getattr(model, self.method_name)(args)

    # ─── Built-in sample tools ─────────────────────────────────────

    @api.model
    def list_overdue_invoices(self, args):
        """Return invoices past due. args: {days_overdue: int}"""
        days = int(args.get("days_overdue", 7))
        cutoff = fields.Date.context_today(self) - timedelta(days=days)
        invs = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("invoice_date_due", "<=", cutoff),
        ], limit=50)
        return [{
            "id": inv.id,
            "name": inv.name,
            "partner": inv.partner_id.name,
            "amount_residual": inv.amount_residual,
            "due_date": str(inv.invoice_date_due),
        } for inv in invs]

    @api.model
    def suggest_reorder(self, args):
        """Identify products below their orderpoint.
        args: {warehouse_code: optional} → list of {product, qty_to_buy}"""
        domain = [("trigger", "=", "auto"), ("active", "=", True)]
        wh_code = args.get("warehouse_code")
        if wh_code:
            domain.append(("warehouse_id.code", "=", wh_code))
        ops = self.env["stock.warehouse.orderpoint"].search(domain, limit=50)
        results = []
        for op in ops:
            qty_avail = op.product_id.qty_available
            if qty_avail < op.product_min_qty:
                results.append({
                    "product": op.product_id.display_name,
                    "default_code": op.product_id.default_code,
                    "qty_available": qty_avail,
                    "min": op.product_min_qty,
                    "max": op.product_max_qty,
                    "qty_to_buy": op.product_max_qty - qty_avail,
                    "warehouse": op.warehouse_id.code,
                })
        return results
