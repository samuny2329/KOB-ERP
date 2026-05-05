"""DeepSeek Active Agent — pulls data itself instead of receiving it passively.

Instead of Claude sending text to DeepSeek, DeepSeek actively decides what tools
to call (obsidian_search, obsidian_read_note, KOB inventory, etc.) and fetches
only what it needs for the task. Returns a concise brief to Claude.

Architecture:
    Claude → spawn_deepseek_agent(task)
                └─ DeepSeek agent loop:
                        DeepSeek calls obsidian_search() if needed
                        DeepSeek calls obsidian_read_note() if needed
                        DeepSeek calls kob_products() if needed
                        ...decides what it needs autonomously...
                └─ returns compressed brief
    Claude receives brief → implements without reading raw files

Env vars:
    DEEPSEEK_API_KEY   - platform.deepseek.com API key
    DEEPSEEK_BASE_URL  - default: https://api.deepseek.com
    DEEPSEEK_MODEL     - default: deepseek-chat
    DEEPSEEK_MAX_ITER  - max tool-call iterations per run (default: 8)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
MAX_ITER = 8


# ── Tool implementations (same logic as obsidian_deepseek.py, callable locally) ──

def _vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not raw:
        raise RuntimeError("OBSIDIAN_VAULT_PATH is not set")
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise RuntimeError(f"Vault path does not exist: {p}")
    return p


def _safe_path(vault: Path, note_path: str) -> Path:
    target = (vault / note_path).resolve()
    if not str(target).startswith(str(vault)):
        raise ValueError(f"Path '{note_path}' escapes vault root")
    return target


def _tool_obsidian_search(query: str, limit: int = 8) -> str:
    import re
    vault = _vault_root()
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results: list[dict] = []
    for md in vault.rglob("*.md"):
        if len(results) >= min(limit, 20):
            break
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(md.stem) or pattern.search(content):
            m = pattern.search(content)
            snippet = ""
            if m:
                s = max(0, m.start() - 60)
                e = min(len(content), m.end() + 120)
                snippet = content[s:e].replace("\n", " ").strip()
            results.append({"path": str(md.relative_to(vault)), "snippet": snippet})
    return json.dumps(results, ensure_ascii=False)


def _tool_obsidian_read(note_path: str) -> str:
    vault = _vault_root()
    target = _safe_path(vault, note_path)
    if not target.exists():
        return f"Note not found: {note_path}"
    return target.read_text(encoding="utf-8", errors="ignore")


def _tool_obsidian_list(folder_path: str = "") -> str:
    vault = _vault_root()
    base = _safe_path(vault, folder_path) if folder_path else vault
    if not base.is_dir():
        return f"Not a directory: {folder_path}"
    items = []
    for e in sorted(base.iterdir()):
        if e.name.startswith("."):
            continue
        rel = str(e.relative_to(vault))
        items.append(f"[dir] {rel}/" if e.is_dir() else f"[note] {rel}")
    return "\n".join(items) or "(empty)"


async def _tool_kob_products(search: str = "") -> str:
    import httpx
    url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    token = os.environ.get("MCP_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"search": search} if search else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{url}/api/v1/wms/products", params=params, headers=headers)
            return r.text
    except Exception as e:
        return f"Backend unavailable: {e}"


async def _tool_kob_inventory(product_id: int | None = None) -> str:
    import httpx
    url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    token = os.environ.get("MCP_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"product_id": product_id} if product_id else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{url}/api/v1/inventory/stock-quants", params=params, headers=headers)
            return r.text
    except Exception as e:
        return f"Backend unavailable: {e}"


# ── Tool schema definitions (OpenAI function calling format) ──────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "obsidian_search",
            "description": "Search Obsidian vault notes by filename and content. Returns list of matching note paths and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {"type": "integer", "description": "Max results (default 8)", "default": 8},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_read_note",
            "description": "Read the full content of an Obsidian note by its relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_path": {"type": "string", "description": "Relative path inside vault, e.g. 'Projects/KOB/vendors.md'"},
                },
                "required": ["note_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_list_folder",
            "description": "List notes and subfolders in an Obsidian vault folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Relative folder path (empty = vault root)", "default": ""},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kob_products",
            "description": "List products from KOB-ERP warehouse system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Optional product name/code filter", "default": ""},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kob_inventory",
            "description": "Query current stock levels from KOB-ERP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "Filter by product ID (optional)"},
                },
            },
        },
    },
]


async def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool call from DeepSeek and return the result string."""
    if name == "obsidian_search":
        return _tool_obsidian_search(**args)
    if name == "obsidian_read_note":
        return _tool_obsidian_read(**args)
    if name == "obsidian_list_folder":
        return _tool_obsidian_list(**args)
    if name == "kob_products":
        return await _tool_kob_products(**args)
    if name == "kob_inventory":
        return await _tool_kob_inventory(**args)
    return f"Unknown tool: {name}"


# ── MCP tool registration ─────────────────────────────────────────────────────

def register_deepseek_agent_tools(mcp: "FastMCP") -> None:
    """Register spawn_deepseek_agent onto the given FastMCP instance."""

    @mcp.tool()
    async def spawn_deepseek_agent(task: str, hint: str = "") -> str:
        """Let DeepSeek actively pull the data it needs to complete a task.

        Unlike compress_with_deepseek (which receives text passively), this tool
        gives DeepSeek access to tools — it decides what to search, read, or query
        from Obsidian and KOB-ERP, then returns a concise brief for Claude to act on.

        task: what you need researched or analysed
              e.g. "Find all vendor contacts related to packaging suppliers"
              e.g. "Summarise open tasks for KOB WMS project from my notes"
              e.g. "What products are low in stock and do I have reorder notes?"

        hint: optional scope hint to help DeepSeek start in the right place
              e.g. "look in Projects/KOB/ folder first"

        Returns a concise brief ready for Claude Opus to implement from.

        Requires DEEPSEEK_API_KEY env var. Get key at platform.deepseek.com ($5 top-up).
        """
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return (
                "DEEPSEEK_API_KEY is not set.\n"
                "1. Sign up at platform.deepseek.com\n"
                "2. Top up $5 (deepseek-chat = $0.14/M tokens)\n"
                "3. Create API key → add DEEPSEEK_API_KEY to .env"
            )

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return "Install openai: uv add openai"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL),
        )
        model = os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL)
        max_iter = int(os.environ.get("DEEPSEEK_MAX_ITER", MAX_ITER))

        system = (
            "You are a research agent for KOB (Kiss of Beauty) business. "
            "You have tools to search and read Obsidian notes and KOB-ERP data. "
            "For the given task: fetch ONLY what is relevant, then produce a "
            "concise brief (bullet points, preserve names/numbers/dates). "
            "Do not fetch more than necessary. When you have enough, stop calling tools and write the brief."
        )

        user_msg = task
        if hint:
            user_msg = f"Hint: {hint}\n\nTask: {task}"

        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

        for iteration in range(max_iter):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=2000,
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop":
                # DeepSeek finished — return the brief
                return choice.message.content or "(no output)"

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                # DeepSeek wants to call tools — execute each and feed results back
                messages.append(choice.message.model_dump(exclude_unset=True))

                for tc in choice.message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        result = await _execute_tool(tc.function.name, args)
                    except Exception as e:
                        result = f"Tool error: {e}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                break

        return f"Agent reached max iterations ({max_iter}). Last response: {choice.message.content or '(none)'}"
