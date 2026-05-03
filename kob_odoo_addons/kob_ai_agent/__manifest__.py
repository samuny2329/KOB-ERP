# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Agentic AI",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Productivity",
    "summary": "Autonomous AI agent — proactive workflow execution. "
               "Backport scaffold of Odoo 20's agentic AI features.",
    "description": """
KOB ERP — Agentic AI
====================
Models + cron + tool-call scaffold for an LLM-driven agent that
proactively monitors KOB ERP state and proposes actions.

Architecture
------------
* ``kob.ai.agent.run`` — one execution row (prompt, model, output, status, cost)
* ``kob.ai.tool`` — registered server tools the agent may call
  (e.g. *list_overdue_invoices*, *suggest_reorder*)
* ``kob.ai.suggestion`` — agent output items that need human approval
  before any write happens; surfaces in the 🔥 Battle Board
* Cron *every 30 min* runs scheduled agents (``trigger='cron'``)
  with whitelisted tools

Safety
------
* All agent writes go through ``kob.ai.suggestion`` first — human approves
* Token & cost cap per run (configurable)
* Tools are explicitly whitelisted by user role
* No raw SQL — only ORM via approved tools

Pre-req
-------
* Set ``ANTHROPIC_API_KEY`` (or ``OPENAI_API_KEY``) env var on Odoo container
* Set ``KOB_AI_MODEL`` (default ``claude-sonnet-4-6``)
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/tools.xml",
        "data/cron.xml",
        "views/agent_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
