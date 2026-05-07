"""Generate 4 KOB WMS spreadsheet dashboards in Sales-style v22 format.

Replaces the existing 4 JSON files in:
    kob_odoo_addons/kob_wms/data/files/

Each dashboard gets:
  - 4 KPI scorecard tiles (top row): keyValue + baseline pointing to Data sheet
  - 1 main chart (line/bar full-width)
  - 2 Top-N tables (left/right) backed by `lists` registry
  - 2 breakdown charts (pie + bar at bottom)

Format: Odoo spreadsheet v22 (matches existing kob_wms files).
Run:    python scripts/build_wms_dashboards.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "kob_odoo_addons" / "kob_wms" / "data" / "files"

LOCALE = {
    "name": "English (US)",
    "code": "en_US",
    "thousandsSeparator": ",",
    "decimalSeparator": ".",
    "weekStart": 7,
    "dateFormat": "m/d/yyyy",
    "timeFormat": "hh:mm:ss a",
}


def fid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── Tile palette (lifted from Odoo Sales dashboard) ──────────────
TILE_BG_BLUE = "#EFF6FF"
TILE_BG_ORANGE = "#FFF7ED"
TILE_BG_GREEN = "#ECFDF5"
TILE_BG_PURPLE = "#F5F3FF"
TILE_BG_RED = "#FEE2E2"

HEADER_TEAL = "#01666b"


def scorecard_figure(
    *,
    fig_id: str,
    x: int,
    y: int,
    width: int = 213,
    height: int = 101,
    title: str,
    key_value_cell: str,
    baseline_cell: str | None = None,
    background: str = TILE_BG_BLUE,
    field_matching: dict | None = None,
) -> dict:
    """KPI scorecard tile.  Positioning uses col=0,row=0 + offset.x/y
    (Odoo 19 spreadsheet anchor-cell pattern). ``x``/``y`` here become
    the offset values."""
    data = {
        "title": {"text": title, "bold": True, "color": "#434343"},
        "background": background,
        "type": "scorecard",
        "keyValue": key_value_cell,
        "baselineMode": "percentage",
        "baselineColorUp": "#00A04A",
        "baselineColorDown": "#DC6965",
        "baseline": baseline_cell or "",
        "baselineDescr": {"text": "vs prior period"} if baseline_cell else {"text": ""},
        "humanize": False,
        "chartId": fig_id,
    }
    if field_matching:
        data["fieldMatching"] = field_matching
    return {
        "id": fig_id,
        "width": width,
        "height": height,
        "tag": "chart",
        "data": data,
        "col": 0,
        "row": 0,
        "offset": {"x": x, "y": y},
    }


def odoo_chart_figure(
    *,
    fig_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    res_model: str,
    measure: str,
    group_by: list[str],
    mode: str = "bar",
    domain: list | None = None,
    order: str | None = "DESC",
    background: str = "#FFFFFF",
    legend_position: str = "right",
    fill_area: bool = False,
    stacked: bool = False,
    field_matching: dict | None = None,
) -> dict:
    """odoo_bar / odoo_pie / odoo_line chart figure (anchor-cell positioning)."""
    data = {
        "title": {"text": title},
        "background": background,
        "legendPosition": legend_position,
        "metaData": {
            "groupBy": group_by,
            "measure": measure,
            "order": order,
            "resModel": res_model,
            "mode": mode,
            "cumulatedStart": False,
        },
        "searchParams": {
            "comparison": None,
            "context": {"group_by": []},
            "domain": domain or [],
            "groupBy": group_by,
            "orderBy": [],
        },
        "type": f"odoo_{mode}",
        "dataSets": [{}],
        "verticalAxisPosition": "left",
        "stacked": stacked,
        "cumulatedStart": False,
        "axesDesign": {},
        "chartId": fig_id,
    }
    if mode == "line":
        data["fillArea"] = fill_area
    if field_matching:
        data["fieldMatching"] = field_matching
    return {
        "id": fig_id,
        "width": width,
        "height": height,
        "tag": "chart",
        "data": data,
        "col": 0,
        "row": 0,
        "offset": {"x": x, "y": y},
    }


def make_list(*, list_id: str, model: str, columns: list[str], domain: list,
              order_by: list[dict], context: dict | None = None,
              name: str = "") -> dict:
    """`lists` registry entry — drives ODOO.LIST formulas in cells.

    Columns are plain field-name strings per Odoo Sales dashboard pattern.
    """
    return {
        "id": list_id,
        "name": name or f"List {list_id}",
        "model": model,
        "columns": columns,
        "domain": domain,
        "context": context or {},
        "orderBy": order_by,
        "fieldMatching": {},
    }


def list_table_cells(*, start_col: str, header_row: int, list_id: str,
                     columns: list[str]) -> tuple[dict, dict]:
    """Generate cells (bare-string formulas) + per-cell style map.

    Returns (cells_dict, styles_map_dict).  Sales schema stores cell
    content as a plain string and references styleId via sheet-level
    ``styles`` mapping (cell or range → integer style ID).
    """
    cells: dict[str, str] = {}
    styles: dict[str, int] = {}
    cols = [chr(ord(start_col) + i) for i in range(len(columns))]
    # Header row — style 2 (bold gray)
    for i, col in enumerate(cols):
        cells[f"{col}{header_row}"] = (
            f'=IFERROR(ODOO.LIST.HEADER({list_id},"{columns[i]}"),"")'
        )
        styles[f"{col}{header_row}"] = 2
    # Data rows 1..10 — style 3 (regular text)
    for row_offset in range(1, 11):
        for i, col in enumerate(cols):
            addr = f"{col}{header_row + row_offset}"
            cells[addr] = (
                f'=IFERROR(ODOO.LIST({list_id},{row_offset},"{columns[i]}"),"")'
            )
            styles[addr] = 3
    return cells, styles


def header_cell(text: str, anchor: str = "A1") -> tuple[dict, dict]:
    """Bold dark-teal section title (style 1).

    Returns (cells, styles) so caller can merge into sheet dicts.
    """
    return ({anchor: text}, {anchor: 1})


# ── Common style block (clone Sales palette, numeric IDs per v22 schema)
# Style IDs:
#   1 — section_title (sheet header H1, bold 16px teal)
#   2 — table_header  (Top-N header row, bold 11px gray)
#   3 — table_cell    (regular text)
STYLES = {
    "1": {
        "bold": True,
        "fontSize": 16,
        "textColor": HEADER_TEAL,
        "align": "left",
    },
    "2": {
        "bold": True,
        "textColor": "#434343",
        "fontSize": 11,
    },
    "3": {
        "textColor": "#01666B",
    },
}


_DATE_GRAN = (":day", ":week", ":month", ":quarter", ":year")


def _has_date_groupby(figure: dict) -> bool:
    """True if chart's groupBy[0] contains a date granularity suffix.

    Odoo 19 spreadsheet ``getChartGranularity`` returns null for charts
    whose first groupBy is not a date field — and ``_onGlobalFilterChange``
    then destructures the null and crashes.  Charts without a date axis
    must NOT carry ``fieldMatching`` for date-type global filters.
    """
    gb = figure.get("data", {}).get("metaData", {}).get("groupBy", [])
    return bool(gb) and any(g.endswith(_DATE_GRAN) for g in gb)


def build_dashboard(
    *,
    title: str,
    global_filter_id: str,
    field_chain: str,
    field_chain_type: str,
    tiles: list[dict] | None = None,
    main_chart: dict,
    list_left: dict,
    list_right: dict,
    list_left_columns: list[str],
    list_right_columns: list[str],
    list_left_title: str,
    list_right_title: str,
    breakdown_left: dict,
    breakdown_right: dict,
) -> dict:
    """Assemble final JSON for one dashboard."""
    tiles = tiles or []
    # Date filter fieldMatching needs `offset: 0` per Sales pattern.
    fm = {global_filter_id: {
        "chain": field_chain,
        "type": field_chain_type,
        "offset": 0,
    }}

    # Charts: only apply fieldMatching when groupBy has a date axis.
    for fig in [main_chart, breakdown_left, breakdown_right] + tiles:
        if _has_date_groupby(fig):
            fig["data"]["fieldMatching"] = fm

    list_left["fieldMatching"] = fm
    list_right["fieldMatching"] = fm

    # Build Dashboard sheet — figures + cells (bare strings) + style map
    cells: dict[str, str] = {}
    sheet_styles: dict[str, int] = {}

    c, s_ = header_cell(title, "B1")
    cells.update(c)
    sheet_styles.update(s_)

    cells["A22"] = list_left_title
    sheet_styles["A22"] = 1
    cells["E22"] = list_right_title
    sheet_styles["E22"] = 1

    c, s_ = list_table_cells(
        start_col="A", header_row=23,
        list_id=list_left["id"], columns=list_left_columns,
    )
    cells.update(c); sheet_styles.update(s_)
    c, s_ = list_table_cells(
        start_col="E", header_row=23,
        list_id=list_right["id"], columns=list_right_columns,
    )
    cells.update(c); sheet_styles.update(s_)

    # Sheet schema cloned from Odoo 19 Sales dashboard exactly.  Missing
    # keys (borders/comments/formats/styles) cause `getColRowOffset` and
    # `getChartGranularity` to read undefined and crash on filter change.
    sheet = {
        "id": fid("sheet"),
        "name": title,
        "isVisible": True,
        "areGridLinesVisible": True,
        "rowNumber": 60,
        "colNumber": 10,
        "rows": {},
        "cols": {},
        "merges": ["B1:I1"],
        "cells": cells,
        "borders": {},
        "comments": {},
        "formats": {},
        "styles": sheet_styles,
        "conditionalFormats": [],
        "figures": tiles + [main_chart, breakdown_left, breakdown_right],
        "tables": [],
        "headerGroups": {"ROW": [], "COL": []},
        "dataValidationRules": [],
    }

    return {
        "version": "18.5.10",
        "sheets": [sheet],
        "styles": STYLES,
        "formats": {},
        "borders": {},
        "customTableStyles": {},
        "revisionId": "START_REVISION",
        "uniqueFigureIds": True,
        "settings": {"locale": LOCALE},
        "pivots": {},
        "pivotNextId": 1,
        "lists": {
            list_left["id"]: list_left,
            list_right["id"]: list_right,
        },
        "listNextId": 3,
        "chartOdooMenusReferences": {},
        "globalFilters": [{
            "id": global_filter_id,
            "type": "date",
            "label": "Date Range",
            "rangeType": "month",
            "defaultValue": {},
        }],
    }


# ─────────────────────────────────────────────────────────────────
# Dashboard 1: WMS Overview
# ─────────────────────────────────────────────────────────────────
def dashboard_overview() -> dict:
    gf = "gf_ov_date"
    chain = "create_date"

    def tile(title, idx, x_off, color, measure, domain, model="wms.sales.order"):
        return scorecard_figure(
            fig_id=fid(f"ov-tile-{idx}"),
            x=18 + x_off, y=60,
            title=title,
            key_value_cell=f"=ODOO.PIVOT.VALUE(\"{idx}\",\"{measure}\")",
            baseline_cell=f"=ODOO.PIVOT.VALUE(\"{idx}b\",\"{measure}\")",
            background=color,
        )

    # Use simpler bar charts as tiles instead of complex pivot scorecards
    # (avoids needing precomputed Data sheet — keep file simple)
    tiles = [
        odoo_chart_figure(
            fig_id=fid("ov-tile1"), x=18, y=60, width=213, height=101,
            title="Total Orders", res_model="wms.sales.order",
            measure="__count", group_by=[], mode="bar",
            domain=[("status", "!=", "cancelled")],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ov-tile2"), x=241, y=60, width=213, height=101,
            title="Fulfilled (Packed/Shipped)", res_model="wms.sales.order",
            measure="__count", group_by=[], mode="bar",
            domain=[("status", "in", ["packed", "shipped"])],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ov-tile3"), x=464, y=60, width=213, height=101,
            title="Items Picked", res_model="wms.sales.order",
            measure="picked_total", group_by=[], mode="bar",
            domain=[("status", "!=", "cancelled")],
            background=TILE_BG_ORANGE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ov-tile4"), x=687, y=60, width=213, height=101,
            title="Pack Cost (฿)", res_model="wms.sales.order",
            measure="total_pack_cost", group_by=[], mode="bar",
            domain=[("status", "in", ["packed", "shipped"])],
            background=TILE_BG_ORANGE, legend_position="none",
        ),
    ]

    main_chart = odoo_chart_figure(
        fig_id=fid("ov-line-daily"),
        x=18, y=171, width=900, height=340,
        title="Daily Order Volume",
        res_model="wms.sales.order",
        measure="__count",
        group_by=["create_date:day"],
        mode="line",
        domain=[("status", "!=", "cancelled")],
        order=None,
        fill_area=True,
        legend_position="none",
    )

    list_left = make_list(
        list_id="1",
        name="Top Customers by Items Picked",
        model="wms.sales.order",
        columns=["customer", "platform", "picked_total"],
        domain=[("status", "not in", ["cancelled"]),
                ("customer", "!=", False)],
        order_by=[{"name": "picked_total", "asc": False}],
    )
    list_right = make_list(
        list_id="2",
        name="Top Products by Picked Qty",
        model="wms.sales.order.line",
        columns=["product_id", "expected_qty", "picked_qty"],
        domain=[("order_id.status", "!=", "cancelled")],
        order_by=[{"name": "picked_qty", "asc": False}],
    )

    breakdown_left = odoo_chart_figure(
        fig_id=fid("ov-pie-platform"),
        x=18, y=800, width=460, height=340,
        title="Orders by Platform",
        res_model="wms.sales.order",
        measure="__count",
        group_by=["platform"],
        mode="pie",
        domain=[("status", "!=", "cancelled")],
    )
    breakdown_right = odoo_chart_figure(
        fig_id=fid("ov-bar-courier"),
        x=488, y=800, width=460, height=340,
        title="Orders by Courier",
        res_model="wms.sales.order",
        measure="__count",
        group_by=["courier_id"],
        mode="bar",
        domain=[("status", "in", ["packed", "shipped"])],
        order="DESC",
    )

    return build_dashboard(
        title="WMS Overview",
        global_filter_id=gf,
        field_chain=chain,
        field_chain_type="datetime",
        tiles=[],
        main_chart=main_chart,
        list_left=list_left,
        list_right=list_right,
        list_left_columns=["customer", "platform", "picked_total"],
        list_right_columns=["product_id", "expected_qty", "picked_qty"],
        list_left_title="Top Customers (by items picked)",
        list_right_title="Top Products (by qty picked)",
        breakdown_left=breakdown_left,
        breakdown_right=breakdown_right,
    )


# ─────────────────────────────────────────────────────────────────
# Dashboard 2: KPI Performance
# ─────────────────────────────────────────────────────────────────
def dashboard_kpi() -> dict:
    gf = "gf_kpi_date"
    chain = "date"

    tiles = [
        odoo_chart_figure(
            fig_id=fid("kpi-tile1"), x=18, y=60, width=213, height=101,
            title="Avg UPH", res_model="wms.worker.performance",
            measure="uph", group_by=[], mode="bar",
            domain=[], background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("kpi-tile2"), x=241, y=60, width=213, height=101,
            title="Total Picks", res_model="wms.worker.performance",
            measure="pick_count", group_by=[], mode="bar",
            domain=[], background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("kpi-tile3"), x=464, y=60, width=213, height=101,
            title="Total Errors", res_model="wms.worker.performance",
            measure="total_errors", group_by=[], mode="bar",
            domain=[], background=TILE_BG_GREEN, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("kpi-tile4"), x=687, y=60, width=213, height=101,
            title="Avg Quality Score", res_model="wms.worker.performance",
            measure="quality_score", group_by=[], mode="bar",
            domain=[], background=TILE_BG_PURPLE, legend_position="none",
        ),
    ]

    main_chart = odoo_chart_figure(
        fig_id=fid("kpi-line-uph"),
        x=18, y=171, width=900, height=340,
        title="Daily UPH Trend",
        res_model="wms.worker.performance",
        measure="uph",
        group_by=["date:day"],
        mode="line",
        domain=[("uph", ">", 0)],
        order=None,
        fill_area=True,
        legend_position="none",
    )

    list_left = make_list(
        list_id="1",
        name="Top Pickers",
        model="wms.worker.performance",
        columns=["kob_user_id", "pick_count", "uph", "error_rate"],
        domain=[("pick_count", ">", 0), ("kob_user_id", "!=", False)],
        order_by=[{"name": "pick_count", "asc": False}],
    )
    list_right = make_list(
        list_id="2",
        name="Top Packers",
        model="wms.worker.performance",
        columns=["kob_user_id", "pack_count", "uph", "quality_score"],
        domain=[("pack_count", ">", 0), ("kob_user_id", "!=", False)],
        order_by=[{"name": "pack_count", "asc": False}],
    )

    breakdown_left = odoo_chart_figure(
        fig_id=fid("kpi-bar-score"),
        x=18, y=800, width=460, height=340,
        title="Worker Score (Top 10)",
        res_model="wms.worker.performance",
        measure="worker_score",
        group_by=["kob_user_id"],
        mode="bar",
        domain=[("kob_user_id", "!=", False)],
        order="DESC",
    )
    breakdown_right = odoo_chart_figure(
        fig_id=fid("kpi-bar-errors"),
        x=488, y=800, width=460, height=340,
        title="Daily Errors",
        res_model="wms.worker.performance",
        measure="total_errors",
        group_by=["date:day"],
        mode="bar",
        domain=[("total_errors", ">", 0)],
    )

    return build_dashboard(
        title="KPI Performance",
        global_filter_id=gf,
        field_chain=chain,
        field_chain_type="date",
        tiles=[],
        main_chart=main_chart,
        list_left=list_left,
        list_right=list_right,
        list_left_columns=["kob_user_id", "pick_count", "uph", "error_rate"],
        list_right_columns=["kob_user_id", "pack_count", "uph", "quality_score"],
        list_left_title="Top Pickers",
        list_right_title="Top Packers",
        breakdown_left=breakdown_left,
        breakdown_right=breakdown_right,
    )


# ─────────────────────────────────────────────────────────────────
# Dashboard 3: Count Adjustments
# ─────────────────────────────────────────────────────────────────
def dashboard_count() -> dict:
    gf = "gf_ca_date"
    chain = "verified_date"

    tiles = [
        odoo_chart_figure(
            fig_id=fid("ca-tile1"), x=18, y=60, width=213, height=101,
            title="Pending Adj.", res_model="wms.count.adjustment",
            measure="__count", group_by=[], mode="bar",
            domain=[("state", "in", ["pending", "approved"])],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ca-tile2"), x=241, y=60, width=213, height=101,
            title="Net Variance Qty", res_model="wms.count.adjustment",
            measure="variance_qty", group_by=[], mode="bar",
            domain=[("state", "!=", "rejected")],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ca-tile3"), x=464, y=60, width=213, height=101,
            title="Avg Variance %", res_model="wms.count.adjustment",
            measure="variance_pct", group_by=[], mode="bar",
            domain=[("state", "!=", "rejected")],
            background=TILE_BG_ORANGE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("ca-tile4"), x=687, y=60, width=213, height=101,
            title="Active Sessions", res_model="wms.count.session",
            measure="__count", group_by=[], mode="bar",
            domain=[("state", "in", ["draft", "in_progress"])],
            background=TILE_BG_ORANGE, legend_position="none",
        ),
    ]

    main_chart = odoo_chart_figure(
        fig_id=fid("ca-bar-state"),
        x=18, y=171, width=900, height=340,
        title="Adjustments by State",
        res_model="wms.count.adjustment",
        measure="__count",
        group_by=["state"],
        mode="bar",
        domain=[],
    )

    list_left = make_list(
        list_id="1",
        name="Top Variance Products",
        model="wms.count.adjustment",
        columns=["product_id", "variance_qty", "variance_pct", "state"],
        domain=[("variance_qty", "!=", 0)],
        order_by=[{"name": "variance_qty", "asc": False}],
    )
    list_right = make_list(
        list_id="2",
        name="Top Variance Locations",
        model="wms.count.adjustment",
        columns=["location_id", "variance_qty", "state"],
        domain=[("variance_qty", "!=", 0)],
        order_by=[{"name": "variance_qty", "asc": False}],
    )

    breakdown_left = odoo_chart_figure(
        fig_id=fid("ca-pie-session"),
        x=18, y=800, width=460, height=340,
        title="Sessions by State",
        res_model="wms.count.session",
        measure="__count",
        group_by=["state"],
        mode="pie",
        domain=[],
    )
    breakdown_right = odoo_chart_figure(
        fig_id=fid("ca-bar-sessiontype"),
        x=488, y=800, width=460, height=340,
        title="Sessions by Type — Done Tasks",
        res_model="wms.count.session",
        measure="done_count",
        group_by=["session_type"],
        mode="bar",
        domain=[],
    )

    return build_dashboard(
        title="Count Adjustments",
        global_filter_id=gf,
        field_chain=chain,
        field_chain_type="datetime",
        tiles=[],
        main_chart=main_chart,
        list_left=list_left,
        list_right=list_right,
        list_left_columns=["product_id", "variance_qty", "variance_pct", "state"],
        list_right_columns=["location_id", "variance_qty", "state"],
        list_left_title="Top Variance Products",
        list_right_title="Top Variance Locations",
        breakdown_left=breakdown_left,
        breakdown_right=breakdown_right,
    )


# ─────────────────────────────────────────────────────────────────
# Dashboard 4: WMS Operations
# ─────────────────────────────────────────────────────────────────
def dashboard_operations() -> dict:
    gf = "gf_op_date"
    chain = "create_date"

    tiles = [
        odoo_chart_figure(
            fig_id=fid("op-tile1"), x=18, y=60, width=213, height=101,
            title="Avg Pick Min", res_model="wms.sales.order",
            measure="pick_duration_min", group_by=[], mode="bar",
            domain=[("pick_duration_min", ">", 0)],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("op-tile2"), x=241, y=60, width=213, height=101,
            title="Avg Pack Min", res_model="wms.sales.order",
            measure="pack_duration_min", group_by=[], mode="bar",
            domain=[("pack_duration_min", ">", 0)],
            background=TILE_BG_BLUE, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("op-tile3"), x=464, y=60, width=213, height=101,
            title="SLA Breached", res_model="wms.sales.order",
            measure="__count", group_by=[], mode="bar",
            domain=[("sla_status", "=", "breached")],
            background=TILE_BG_RED, legend_position="none",
        ),
        odoo_chart_figure(
            fig_id=fid("op-tile4"), x=687, y=60, width=213, height=101,
            title="Avg Pack Cost (฿)", res_model="wms.sales.order",
            measure="total_pack_cost", group_by=[], mode="bar",
            domain=[("status", "in", ["packed", "shipped"])],
            background=TILE_BG_GREEN, legend_position="none",
        ),
    ]

    main_chart = odoo_chart_figure(
        fig_id=fid("op-line-duration"),
        x=18, y=171, width=900, height=340,
        title="Daily Avg Total Duration (min)",
        res_model="wms.sales.order",
        measure="total_duration_min",
        group_by=["create_date:day"],
        mode="line",
        domain=[("total_duration_min", ">", 0)],
        order=None,
        fill_area=True,
        legend_position="none",
    )

    list_left = make_list(
        list_id="1",
        name="Recent SLA Breaches",
        model="wms.sales.order",
        columns=["display_order_name", "platform", "sla_status",
                 "total_duration_min"],
        domain=[("sla_status", "=", "breached")],
        order_by=[{"name": "create_date", "asc": False}],
    )
    list_right = make_list(
        list_id="2",
        name="Slowest Active Orders",
        model="wms.sales.order",
        columns=["display_order_name", "status", "pick_duration_min",
                 "pack_duration_min"],
        domain=[("status", "in", ["picking", "packing"])],
        order_by=[{"name": "total_duration_min", "asc": False}],
    )

    breakdown_left = odoo_chart_figure(
        fig_id=fid("op-pie-sla"),
        x=18, y=800, width=460, height=340,
        title="SLA Status Mix",
        res_model="wms.sales.order",
        measure="__count",
        group_by=["sla_status"],
        mode="pie",
        domain=[("status", "!=", "cancelled")],
    )
    breakdown_right = odoo_chart_figure(
        fig_id=fid("op-bar-courier"),
        x=488, y=800, width=460, height=340,
        title="Courier Throughput",
        res_model="wms.courier.batch",
        measure="__count",
        group_by=["courier_id"],
        mode="bar",
        domain=[],
        order="DESC",
    )

    return build_dashboard(
        title="WMS Operations",
        global_filter_id=gf,
        field_chain=chain,
        field_chain_type="datetime",
        tiles=[],
        main_chart=main_chart,
        list_left=list_left,
        list_right=list_right,
        list_left_columns=["display_order_name", "platform", "sla_status",
                           "total_duration_min"],
        list_right_columns=["display_order_name", "status",
                            "pick_duration_min", "pack_duration_min"],
        list_left_title="Recent SLA Breaches",
        list_right_title="Slowest Active Orders",
        breakdown_left=breakdown_left,
        breakdown_right=breakdown_right,
    )


# ─────────────────────────────────────────────────────────────────
DASHBOARDS = [
    ("kob_wms_dashboard.json", dashboard_overview),
    ("kob_wms_kpi_dashboard.json", dashboard_kpi),
    ("kob_wms_count_dashboard.json", dashboard_count),
    ("kob_wms_operations_dashboard.json", dashboard_operations),
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing dashboards to: {OUT_DIR}")
    for filename, builder in DASHBOARDS:
        data = builder()
        out = OUT_DIR / filename
        out.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        size = out.stat().st_size
        figs = sum(len(s["figures"]) for s in data["sheets"])
        lists_n = len(data["lists"])
        print(f"  [OK] {filename}: {size:,} bytes, {figs} figures, "
              f"{lists_n} lists")
    print("Done.")


if __name__ == "__main__":
    main()
