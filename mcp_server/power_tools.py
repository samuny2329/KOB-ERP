"""Power tools: RTK, CAVEMAN, KRAPHIFY.

RTK (Research Tool Kit)
    Multi-source research in one call: Obsidian + KOB-ERP + web (DuckDuckGo).
    Returns a merged brief from all three sources.

CAVEMAN
    Brute-force vault reader. Reads every .md file in a folder without filtering.
    Use when you don't know where the data is. Raw dump → feed to DeepSeek/Hermes.

KRAPHIFY
    Knowledge graph builder. Parses [[wikilinks]] across the Obsidian vault and
    maps relationships between notes. Helps Claude see the big picture before diving in.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not raw:
        raise RuntimeError("OBSIDIAN_VAULT_PATH is not set")
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise RuntimeError(f"Vault path does not exist: {p}")
    return p


def _safe_path(vault: Path, rel: str) -> Path:
    target = (vault / rel).resolve()
    if not str(target).startswith(str(vault)):
        raise ValueError(f"Path '{rel}' escapes vault root")
    return target


# ── RTK helpers ───────────────────────────────────────────────────────────────

async def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo instant answer API — no key required."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "KOB-ERP-MCP/1.0"},
            )
            data = r.json()
    except Exception as e:
        return [{"source": "web", "title": "Error", "snippet": str(e)}]

    results: list[dict] = []
    if data.get("AbstractText"):
        results.append({
            "source": data.get("AbstractSource", "web"),
            "title": data.get("Heading", query),
            "snippet": data["AbstractText"][:400],
            "url": data.get("AbstractURL", ""),
        })
    for item in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(item, dict) and item.get("Text"):
            results.append({
                "source": "duckduckgo",
                "title": item.get("Text", "")[:80],
                "snippet": item.get("Text", "")[:300],
                "url": item.get("FirstURL", ""),
            })
    return results[:max_results]


async def _kob_search(query: str) -> list[dict]:
    url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    token = os.environ.get("MCP_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{url}/api/v1/wms/products",
                params={"search": query},
                headers=headers,
            )
            items = r.json() if r.status_code == 200 else []
            for item in (items if isinstance(items, list) else [])[:5]:
                results.append({
                    "source": "kob-erp",
                    "title": item.get("name", ""),
                    "snippet": f"SKU: {item.get('default_code','')} | Type: {item.get('type','')}",
                })
    except Exception:
        pass
    return results


def _obsidian_search_sync(query: str, limit: int = 5) -> list[dict]:
    try:
        vault = _vault_root()
    except RuntimeError:
        return []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results = []
    for md in vault.rglob("*.md"):
        if len(results) >= limit:
            break
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(md.stem) or pattern.search(content):
            m = pattern.search(content)
            snippet = ""
            if m:
                s, e = max(0, m.start() - 60), min(len(content), m.end() + 150)
                snippet = content[s:e].replace("\n", " ").strip()
            results.append({
                "source": "obsidian",
                "title": md.stem,
                "path": str(md.relative_to(vault)),
                "snippet": snippet,
            })
    return results


# ── KRAPHIFY helpers ──────────────────────────────────────────────────────────

_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def _build_graph(vault: Path, folder: str = "") -> dict[str, list[str]]:
    base = _safe_path(vault, folder) if folder else vault
    graph: dict[str, list[str]] = {}

    for md in base.rglob("*.md"):
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        node = md.stem
        links = list({m.group(1).strip() for m in _WIKILINK.finditer(content)})
        graph[node] = links

    return graph


def _graph_summary(graph: dict[str, list[str]], top_n: int = 20) -> str:
    if not graph:
        return "No notes with [[wikilinks]] found."

    # rank by in-degree (most referenced notes)
    in_degree: dict[str, int] = {}
    for links in graph.values():
        for link in links:
            in_degree[link] = in_degree.get(link, 0) + 1

    hub_notes = sorted(in_degree.items(), key=lambda x: -x[1])[:top_n]
    isolated = [n for n, links in graph.items() if not links and not in_degree.get(n)]

    lines = [
        f"Total notes: {len(graph)}",
        f"Notes with outgoing links: {sum(1 for v in graph.values() if v)}",
        "",
        "── Top hub notes (most referenced) ──",
    ]
    for name, count in hub_notes:
        lines.append(f"  [{count}x] {name}")

    lines += ["", "── Full link map (note → links) ──"]
    for note, links in sorted(graph.items()):
        if links:
            lines.append(f"  {note} → {', '.join(links)}")

    if isolated:
        lines += ["", f"── Isolated notes (no links, {len(isolated)} total) ──"]
        lines.append("  " + ", ".join(isolated[:30]))
        if len(isolated) > 30:
            lines.append(f"  ...and {len(isolated) - 30} more")

    return "\n".join(lines)


# ── Tool registration ─────────────────────────────────────────────────────────

def register_power_tools(mcp: "FastMCP") -> None:

    @mcp.tool()
    async def rtk(query: str, web: bool = True, obsidian: bool = True, kob: bool = True) -> str:
        """RTK (Research Tool Kit) — multi-source research in one call.

        Searches up to three sources simultaneously:
        - web:      DuckDuckGo instant answers (no API key needed)
        - obsidian: local Obsidian vault notes
        - kob:      KOB-ERP product/warehouse database

        Returns a merged brief from all enabled sources.

        query:    what to research
        web:      include web results (default True)
        obsidian: include Obsidian vault (default True)
        kob:      include KOB-ERP backend (default True)
        """
        sections: list[str] = [f"RTK Research: '{query}'\n"]

        import asyncio
        tasks = []
        labels = []

        if web:
            tasks.append(_ddg_search(query))
            labels.append("WEB")
        if kob:
            tasks.append(_kob_search(query))
            labels.append("KOB-ERP")

        results_list = await asyncio.gather(*tasks)

        for label, results in zip(labels, results_list):
            sections.append(f"── {label} ──")
            if results:
                for r in results:
                    sections.append(f"  [{r.get('source','')}] {r.get('title','')}")
                    if r.get("snippet"):
                        sections.append(f"    {r['snippet'][:250]}")
                    if r.get("url"):
                        sections.append(f"    → {r['url']}")
            else:
                sections.append("  (no results)")

        if obsidian:
            sections.append("── OBSIDIAN ──")
            obs = _obsidian_search_sync(query)
            if obs:
                for r in obs:
                    sections.append(f"  [{r['path']}] {r['title']}")
                    if r.get("snippet"):
                        sections.append(f"    …{r['snippet'][:200]}…")
            else:
                sections.append("  (no matching notes)")

        return "\n".join(sections)

    @mcp.tool()
    async def caveman(folder_path: str = "", max_files: int = 30) -> str:
        """CAVEMAN — brute-force vault reader. Reads everything in a folder.

        Dumps raw content of all .md files without filtering or summarizing.
        Use when you have no idea where the relevant data is.
        Feed the output to spawn_deepseek_agent or spawn_hermes for compression.

        folder_path: relative path inside vault (empty = vault root)
        max_files:   safety limit (default 30, max 100)

        Warning: output can be very large. Consider compress_with_deepseek after.
        """
        try:
            vault = _vault_root()
        except RuntimeError as e:
            return str(e)

        max_files = min(max_files, 100)
        base = _safe_path(vault, folder_path) if folder_path else vault

        if not base.is_dir():
            return f"Not a directory: {folder_path}"

        parts: list[str] = [f"CAVEMAN DUMP — {folder_path or 'vault root'}\n"]
        count = 0

        for md in sorted(base.rglob("*.md")):
            if count >= max_files:
                parts.append(f"\n[stopped at {max_files} files — use folder_path to narrow scope]")
                break
            rel = str(md.relative_to(vault))
            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            parts.append(f"\n{'='*60}\n[FILE: {rel}]\n{'='*60}\n{content}")
            count += 1

        parts.append(f"\n\nTotal files dumped: {count}")
        return "\n".join(parts)

    @mcp.tool()
    async def kraphify(folder_path: str = "", format: str = "summary") -> str:
        """KRAPHIFY — build a knowledge graph from Obsidian [[wikilinks]].

        Scans all notes for [[wikilinks]], maps connections between topics,
        and identifies hub notes (most referenced). Helps Claude understand
        the structure of your knowledge base before diving into specific notes.

        folder_path: scope to a subfolder (empty = entire vault)
        format:      "summary" (default) | "json" (raw adjacency map)

        Returns:
          summary — ranked hub notes + full link map + isolated notes
          json    — raw {note: [linked_notes]} dict for programmatic use
        """
        try:
            vault = _vault_root()
        except RuntimeError as e:
            return str(e)

        graph = _build_graph(vault, folder_path)

        if not graph:
            return "No .md files found in the specified path."

        if format == "json":
            return json.dumps(graph, ensure_ascii=False, indent=2)

        return _graph_summary(graph)
