"""KOB-ERP MCP server.

Exposes warehouse + inventory + order operations as tools that Claude (or any
MCP-compatible AI) can call directly.  Run with:

    uv run python -m mcp_server.server

Requires the backend to be reachable at BACKEND_URL (default http://localhost:8000).
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise RuntimeError("Install mcp: uv add 'mcp[cli]'")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_TOKEN = os.getenv("MCP_API_TOKEN", "")

mcp = FastMCP("KOB-ERP", instructions="ERP operations for KOB warehouse management system")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


async def _get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BACKEND_URL}{path}", params=params, headers=_headers())
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BACKEND_URL}{path}", json=body, headers=_headers())
        r.raise_for_status()
        return r.json()


# ── Inventory tools ────────────────────────────────────────────────────


@mcp.tool()
async def query_inventory(
    product_id: int | None = None,
    location_id: int | None = None,
) -> str:
    """Query current on-hand stock levels.

    Returns a JSON list of stock quants filtered by product and/or location.
    """
    params: dict[str, Any] = {}
    if product_id:
        params["product_id"] = product_id
    if location_id:
        params["location_id"] = location_id
    data = await _get("/api/v1/inventory/stock-quants", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_products(search: str | None = None) -> str:
    """List products in the WMS catalogue.  Optionally filter by name/code."""
    params = {}
    if search:
        params["search"] = search
    data = await _get("/api/v1/wms/products", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_warehouses() -> str:
    """List all active warehouses."""
    data = await _get("/api/v1/wms/warehouses")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Transfer tools ────────────────────────────────────────────────────


@mcp.tool()
async def create_transfer(
    transfer_type_id: int,
    lines: list[dict],
    notes: str | None = None,
) -> str:
    """Create a new stock transfer.

    lines: list of {product_id, qty_demand, uom_id?}
    Returns the created transfer with its ID and state.
    """
    body: dict[str, Any] = {
        "transfer_type_id": transfer_type_id,
        "lines": lines,
    }
    if notes:
        body["notes"] = notes
    data = await _post("/api/v1/inventory/transfers", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def confirm_transfer(transfer_id: int) -> str:
    """Confirm a draft transfer (moves state draft → confirmed)."""
    data = await _post(f"/api/v1/inventory/transfers/{transfer_id}/confirm", {})
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def complete_transfer(transfer_id: int) -> str:
    """Validate / complete a confirmed transfer and update stock quants."""
    data = await _post(f"/api/v1/inventory/transfers/{transfer_id}/done", {})
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Purchase tools ────────────────────────────────────────────────────


@mcp.tool()
async def create_purchase_order(
    vendor_id: int,
    order_date: str,
    lines: list[dict],
    notes: str | None = None,
) -> str:
    """Create a purchase order.

    lines: list of {product_id, qty_ordered, unit_price, uom_id?}
    order_date: ISO date string e.g. "2026-01-15"
    """
    import uuid

    body: dict[str, Any] = {
        "number": f"PO-{uuid.uuid4().hex[:8].upper()}",
        "vendor_id": vendor_id,
        "order_date": order_date,
        "lines": lines,
    }
    if notes:
        body["notes"] = notes
    data = await _post("/api/v1/purchase/orders", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_purchase_orders(state: str | None = None) -> str:
    """List purchase orders, optionally filtered by state."""
    params = {}
    if state:
        params["state"] = state
    data = await _get("/api/v1/purchase/orders", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Sales tools ───────────────────────────────────────────────────────


@mcp.tool()
async def create_sales_order(
    customer_id: int,
    order_date: str,
    lines: list[dict],
    notes: str | None = None,
) -> str:
    """Create a sales order.

    lines: list of {product_id, qty_ordered, unit_price, discount_pct?}
    """
    import uuid

    body: dict[str, Any] = {
        "number": f"SO-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": customer_id,
        "order_date": order_date,
        "lines": lines,
    }
    if notes:
        body["notes"] = notes
    data = await _post("/api/v1/sales/orders", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_sales_orders(state: str | None = None) -> str:
    """List sales orders, optionally filtered by state."""
    params = {}
    if state:
        params["state"] = state
    data = await _get("/api/v1/sales/orders", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Subcon recon tools ────────────────────────────────────────────────


@mcp.tool()
async def list_subcon_recons() -> str:
    """List subcontractor reconciliation sessions."""
    data = await _get("/api/v1/mfg/subcon-recons")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── HR tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def list_employees(department_id: int | None = None) -> str:
    """List employees, optionally filtered by department."""
    params = {}
    if department_id:
        params["department_id"] = department_id
    data = await _get("/api/v1/hr/employees", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_worker_kpis(user_id: int | None = None) -> str:
    """Get worker KPI metrics."""
    params = {}
    if user_id:
        params["user_id"] = user_id
    data = await _get("/api/v1/ops/kpi/workers", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Audit tools ───────────────────────────────────────────────────────


@mcp.tool()
async def verify_audit_chain() -> str:
    """Verify the integrity of the hash-chain activity log.

    Returns OK if the chain is intact, or the ID of the first broken block.
    """
    data = await _get("/api/v1/audit/activity-log/verify")
    return json.dumps(data, ensure_ascii=False, indent=2)


from mcp_server.obsidian_deepseek import register_obsidian_tools
from mcp_server.subagent import register_subagent_tools
from mcp_server.deepseek_agent import register_deepseek_agent_tools

register_obsidian_tools(mcp)
register_subagent_tools(mcp)
register_deepseek_agent_tools(mcp)

if __name__ == "__main__":
    mcp.run()
