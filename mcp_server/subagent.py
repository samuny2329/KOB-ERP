"""Claude Opus 4.7 sub-agent tool for KOB-ERP MCP server.

Registers a `spawn_subagent` MCP tool that lets the orchestrating Claude session
delegate heavy research or analysis tasks to Claude Opus 4.7 via the Anthropic API.

Architecture:
    User prompt → Claude Sonnet (orchestrator, has tool access)
                  └─ spawn_subagent(task, context) ─→ Claude Opus 4.7
                                                       (text-only, returns brief)
                  ← brief string ←─────────────────────┘
    Claude Sonnet implements using the compressed brief

Why Opus as the worker (not Haiku)?
    Opus 4.7 understands KOB business domain and Thai context deeply.
    DeepSeek compresses the raw Obsidian/file content first (cheap),
    then Opus receives a short brief → cost stays low while quality is maximum.

Env vars:
    ANTHROPIC_API_KEY  - Anthropic console API key
    SUBAGENT_MODEL     - default: claude-opus-4-7 (override for testing with haiku)
    SUBAGENT_MAX_TOKENS - default: 4096
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096


def _anthropic_client():
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise RuntimeError("Install anthropic: uv add anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is not set")

    return AsyncAnthropic(api_key=api_key)


def register_subagent_tools(mcp: "FastMCP") -> None:
    """Register spawn_subagent onto the given FastMCP instance."""

    @mcp.tool()
    async def spawn_subagent(
        task_prompt: str,
        context: str = "",
        model: str = "",
    ) -> str:
        """Delegate a research or analysis task to Claude Opus 4.7.

        Use this when the task requires deep understanding but would consume too
        many tokens if Claude Sonnet read everything raw. Typical flow:

        1. Call research_and_compress() to get a brief from Obsidian/DeepSeek
        2. Call spawn_subagent(task_prompt=<what to do>, context=<brief>)
        3. Opus returns a focused analysis or plan
        4. Use that plan to implement in the current session

        task_prompt:  the specific question or task for the sub-agent
        context:      pre-compressed background (from research_and_compress or similar)
        model:        override model ID (default: claude-opus-4-7)

        Returns the sub-agent's full text response.

        Cost note: Opus 4.7 = $15/M input. Pass a compressed context (< 5K tokens)
        to keep cost under $0.10 per call.
        """
        client = _anthropic_client()
        resolved_model = model or os.environ.get("SUBAGENT_MODEL", DEFAULT_MODEL)
        max_tokens = int(os.environ.get("SUBAGENT_MAX_TOKENS", DEFAULT_MAX_TOKENS))

        if context.strip():
            user_content = f"<context>\n{context.strip()}\n</context>\n\n{task_prompt}"
        else:
            user_content = task_prompt

        response = await client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=(
                "You are an expert KOB business analyst and software architect. "
                "You receive a compressed context brief and a task. "
                "Produce a precise, actionable response. "
                "If asked for a plan, return numbered steps. "
                "If asked for analysis, use bullet points with specific details. "
                "Write in the same language as the task_prompt (Thai or English)."
            ),
            messages=[{"role": "user", "content": user_content}],
        )

        return response.content[0].text  # type: ignore[union-attr]
