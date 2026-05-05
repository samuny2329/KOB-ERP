"""Obsidian vault reader + DeepSeek context compression tools.

Registers MCP tools for reading local Obsidian .md files and compressing
large note collections into concise briefs using DeepSeek (OpenAI-compatible API).

Env vars:
    OBSIDIAN_VAULT_PATH  - absolute path to Obsidian vault root
    DEEPSEEK_API_KEY     - DeepSeek platform API key
    DEEPSEEK_BASE_URL    - default: https://api.deepseek.com
    DEEPSEEK_MODEL       - default: deepseek-chat
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not raw:
        raise RuntimeError("OBSIDIAN_VAULT_PATH env var is not set")
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH does not exist: {p}")
    return p


def _safe_path(vault: Path, note_path: str) -> Path:
    """Resolve note_path inside vault; raise if it escapes the vault."""
    target = (vault / note_path).resolve()
    if not str(target).startswith(str(vault)):
        raise ValueError(f"Path '{note_path}' escapes the vault root")
    return target


def _deepseek_client():
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("Install openai: uv add openai")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY env var is not set")

    return AsyncOpenAI(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


def register_obsidian_tools(mcp: "FastMCP") -> None:
    """Register all Obsidian + DeepSeek tools onto the given FastMCP instance."""

    @mcp.tool()
    async def obsidian_list_folder(folder_path: str = "") -> str:
        """List .md files and sub-folders inside an Obsidian vault folder.

        folder_path: relative path inside the vault (empty string = vault root).
        Returns a newline-separated list of paths.
        """
        vault = _vault_root()
        base = _safe_path(vault, folder_path) if folder_path else vault
        if not base.is_dir():
            return f"Not a directory: {folder_path}"

        items: list[str] = []
        for entry in sorted(base.iterdir()):
            if entry.name.startswith("."):
                continue
            rel = str(entry.relative_to(vault))
            if entry.is_dir():
                items.append(f"[dir]  {rel}/")
            elif entry.suffix == ".md":
                items.append(f"[note] {rel}")
        return "\n".join(items) if items else "(empty folder)"

    @mcp.tool()
    async def obsidian_search(query: str, limit: int = 10) -> str:
        """Search Obsidian vault notes by filename and content (case-insensitive).

        Returns a JSON-like list of matched notes with path and a short snippet.
        limit: max results (default 10, max 50).
        """
        vault = _vault_root()
        limit = min(limit, 50)
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        results: list[dict] = []

        for md_file in vault.rglob("*.md"):
            if len(results) >= limit:
                break
            rel = str(md_file.relative_to(vault))
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            title_match = pattern.search(md_file.stem)
            content_match = pattern.search(content)
            if not title_match and not content_match:
                continue

            # extract a short snippet around first match
            snippet = ""
            if content_match:
                start = max(0, content_match.start() - 80)
                end = min(len(content), content_match.end() + 160)
                snippet = content[start:end].replace("\n", " ").strip()

            results.append({"path": rel, "title": md_file.stem, "snippet": snippet})

        if not results:
            return f"No notes found matching '{query}'"

        lines = [f"Found {len(results)} note(s) matching '{query}':\n"]
        for r in results:
            lines.append(f"  [{r['path']}] {r['title']}")
            if r["snippet"]:
                lines.append(f"    …{r['snippet']}…")
        return "\n".join(lines)

    @mcp.tool()
    async def obsidian_read_note(note_path: str) -> str:
        """Read the full content of an Obsidian note.

        note_path: relative path inside the vault, e.g. "Projects/KOB/vendors.md"
        """
        vault = _vault_root()
        target = _safe_path(vault, note_path)
        if not target.exists():
            return f"Note not found: {note_path}"
        if target.suffix != ".md":
            return f"Not a markdown file: {note_path}"
        return target.read_text(encoding="utf-8", errors="ignore")

    @mcp.tool()
    async def compress_with_deepseek(content: str, compression_goal: str) -> str:
        """Use DeepSeek to compress/summarize a large block of text.

        content:          the raw text to compress (e.g. several Obsidian notes)
        compression_goal: what to extract, e.g. "summarize vendor contacts" or
                          "extract all open tasks and deadlines"

        Returns a concise brief (~500-1000 words) optimised for the goal.
        Cost: ~$0.14 per 1M input tokens (deepseek-chat).
        """
        client = _deepseek_client()
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

        system = (
            "You are a precision context compressor. "
            "Given raw notes or documents, extract ONLY information relevant to the user's goal. "
            "Be concise. Use bullet points. Preserve names, numbers, dates. "
            "Output plain text, no markdown headers."
        )
        user_msg = f"GOAL: {compression_goal}\n\n---\n\n{content}"

        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1500,
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    @mcp.tool()
    async def research_and_compress(
        query: str,
        compression_goal: str,
        max_notes: int = 5,
    ) -> str:
        """Search Obsidian vault, read top notes, then compress with DeepSeek.

        This is the main power tool:
        1. Search vault for `query`
        2. Read up to `max_notes` matching notes
        3. Feed all content to DeepSeek with `compression_goal`
        4. Return a concise brief ready for Claude Opus to act on

        max_notes: 1-10 (default 5)
        """
        vault = _vault_root()
        max_notes = min(max(max_notes, 1), 10)
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matched: list[Path] = []

        for md_file in vault.rglob("*.md"):
            if len(matched) >= max_notes:
                break
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern.search(md_file.stem) or pattern.search(content):
                matched.append(md_file)

        if not matched:
            return f"No notes found matching '{query}'. Cannot compress."

        combined_parts: list[str] = []
        for f in matched:
            rel = str(f.relative_to(vault))
            text = f.read_text(encoding="utf-8", errors="ignore")
            combined_parts.append(f"=== {rel} ===\n{text}")

        combined = "\n\n".join(combined_parts)
        note_list = ", ".join(str(f.relative_to(vault)) for f in matched)

        brief = await compress_with_deepseek(combined, compression_goal)  # type: ignore[name-defined]
        return f"[Sources: {note_list}]\n\n{brief}"
