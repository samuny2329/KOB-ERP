"""Sub-agent tools for KOB-ERP MCP server.

Two sub-agent tools available:
  - spawn_subagent   → Claude Opus 4.7 via Anthropic API (deep reasoning)
  - spawn_hermes     → Hermes 4 via OpenRouter (free tier, fast analysis)

Architecture:
    Claude (orchestrator) → spawn_subagent / spawn_hermes
                                └─ model receives compressed context
                                └─ returns focused brief
    Claude implements using the brief

Env vars:
    ANTHROPIC_API_KEY    - console.anthropic.com (for Opus)
    SUBAGENT_MODEL       - default: claude-opus-4-7
    SUBAGENT_MAX_TOKENS  - default: 4096

    OPENROUTER_API_KEY   - openrouter.ai (for Hermes 4, has free tier)
    HERMES_MODEL         - default: nousresearch/hermes-3-llama-3.1-405b
    HERMES_MAX_TOKENS    - default: 4096
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# ── Anthropic (Opus) ──────────────────────────────────────────────────────────

DEFAULT_OPUS_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096

OPUS_SYSTEM = (
    "You are an expert KOB business analyst and software architect. "
    "You receive a compressed context brief and a task. "
    "Produce a precise, actionable response. "
    "If asked for a plan, return numbered steps. "
    "If asked for analysis, use bullet points with specific details. "
    "Write in the same language as the task_prompt (Thai or English)."
)

# ── OpenRouter (Hermes 4) ─────────────────────────────────────────────────────

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_HERMES_MODEL = "nousresearch/hermes-3-llama-3.1-405b"

HERMES_SYSTEM = (
    "You are Hermes, a highly capable assistant and KOB business analyst. "
    "You follow instructions precisely and think step by step. "
    "When given a compressed context, extract the most relevant details for the task. "
    "Be concise and structured. Use bullet points or numbered steps. "
    "Match the language of the user's request (Thai or English)."
)


def _anthropic_client():
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise RuntimeError("Install anthropic: uv add anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return AsyncAnthropic(api_key=api_key)


def _openrouter_client():
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("Install openai: uv add openai")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set.\n"
            "1. Sign up at openrouter.ai\n"
            "2. Get free API key (has free-tier models)\n"
            "3. Add OPENROUTER_API_KEY to .env"
        )
    return AsyncOpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def register_subagent_tools(mcp: "FastMCP") -> None:

    @mcp.tool()
    async def spawn_subagent(
        task_prompt: str,
        context: str = "",
        model: str = "",
    ) -> str:
        """Delegate a task to Claude Opus 4.7 (deep reasoning, highest quality).

        Best for: complex analysis, architecture decisions, Thai business context.

        task_prompt: the task for the sub-agent
        context:     pre-compressed background (from research_and_compress or spawn_deepseek_agent)
        model:       override model ID (default: claude-opus-4-7)

        Cost: $15/M input — pass compressed context (<5K tokens) to keep under $0.10/call.
        Requires ANTHROPIC_API_KEY with credits.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return (
                "ANTHROPIC_API_KEY is not set.\n"
                "Sign up at console.anthropic.com and add credits."
            )

        client = _anthropic_client()
        resolved_model = model or os.environ.get("SUBAGENT_MODEL", DEFAULT_OPUS_MODEL)
        max_tokens = int(os.environ.get("SUBAGENT_MAX_TOKENS", DEFAULT_MAX_TOKENS))

        user_content = (
            f"<context>\n{context.strip()}\n</context>\n\n{task_prompt}"
            if context.strip()
            else task_prompt
        )

        response = await client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=OPUS_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text  # type: ignore[union-attr]

    @mcp.tool()
    async def spawn_hermes(
        task_prompt: str,
        context: str = "",
        model: str = "",
    ) -> str:
        """Delegate a task to Hermes 4 (NousResearch) via OpenRouter.

        Hermes 4 is a powerful open-source model available with a free tier on OpenRouter.
        Best for: fast analysis, structured output, reasoning tasks, when Anthropic credits
        are unavailable or for cost-sensitive workloads.

        task_prompt: the task for Hermes
        context:     pre-compressed background (from research_and_compress or spawn_deepseek_agent)
        model:       override model ID (default: nousresearch/hermes-3-llama-3.1-405b)

        Free tier available at openrouter.ai — no credit card required for free models.
        Requires OPENROUTER_API_KEY.
        """
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return (
                "OPENROUTER_API_KEY is not set.\n"
                "1. Sign up at openrouter.ai (free)\n"
                "2. Create API key\n"
                "3. Add OPENROUTER_API_KEY to .env\n"
                "Free-tier models available — no top-up needed to start."
            )

        client = _openrouter_client()
        resolved_model = model or os.environ.get("HERMES_MODEL", DEFAULT_HERMES_MODEL)
        max_tokens = int(os.environ.get("HERMES_MAX_TOKENS", DEFAULT_MAX_TOKENS))

        user_content = (
            f"<context>\n{context.strip()}\n</context>\n\n{task_prompt}"
            if context.strip()
            else task_prompt
        )

        response = await client.chat.completions.create(
            model=resolved_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": HERMES_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com/samuny2329/kob-erp",
                "X-Title": "KOB-ERP MCP",
            },
        )
        return response.choices[0].message.content or ""
