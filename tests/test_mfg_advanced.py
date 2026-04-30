"""Tests for advanced manufacturing models — Odoo 19 parity + KOB-exclusive."""

import pytest

from backend.modules.mfg.models import (
    BomLine,
    BomTemplate,
    ManufacturingOrder,
    MO_STATES,
    BOM_LINE_TYPES,
    SubconVendor,
    WorkOrder,
)
from backend.modules.mfg.models_advanced import (
    BatchConsolidation,
    MoComponentLine,
    MoProductionSignal,
    MoScrap,
    ProductionShift,
    Routing,
    RoutingOperation,
    UnbuildOrder,
    WorkCenter,
    WorkCenterOee,
)
from backend.modules.mfg.service import compute_oee


# ── MO model structure ─────────────────────────────────────────────────


def test_mo_states_includes_to_close():
    assert "to_close" in MO_STATES
    assert "in_progress" in MO_STATES
    assert "done" in MO_STATES
    assert "cancelled" in MO_STATES


def test_mo_state_machine_transitions():
    assert "to_close" in ManufacturingOrder.allowed_transitions["in_progress"]
    assert "done" in ManufacturingOrder.allowed_transitions["to_close"]
    assert "in_progress" in ManufacturingOrder.allowed_transitions["to_close"]
    assert ManufacturingOrder.allowed_transitions["done"] == set()


def test_mo_has_cost_fields():
    cols = {c.key for c in ManufacturingOrder.__table__.columns}
    assert "material_cost" in cols
    assert "labor_cost" in cols
    assert "overhead_cost" in cols
    assert "total_cost" in cols
    assert "qty_scrap" in cols
    assert "lot_id" in cols
    assert "scheduled_start" in cols
    assert "scheduled_end" in cols


def test_mo_has_subcon_link():
    cols = {c.key for c in ManufacturingOrder.__table__.columns}
    assert "subcon_recon_id" in cols


def test_bom_line_types():
    assert "component" in BOM_LINE_TYPES
    assert "byproduct" in BOM_LINE_TYPES
    assert "phantom" in BOM_LINE_TYPES


def test_bom_line_has_new_fields():
    cols = {c.key for c in BomLine.__table__.columns}
    assert "line_type" in cols
    assert "sequence" in cols
    assert "country_of_origin" in cols
    assert "hs_code" in cols


def test_bom_template_versioning_fields():
    cols = {c.key for c in BomTemplate.__table__.columns}
    assert "version" in cols
    assert "effective_from" in cols
    assert "effective_to" in cols
    assert "routing_id" in cols


def test_work_order_new_fields():
    cols = {c.key for c in WorkOrder.__table__.columns}
    assert "work_center_id" in cols
    assert "setup_duration" in cols
    assert "remaining_minutes" in cols
    assert "planned_end" in cols
    assert "sequence" in cols
    assert "shift_id" in cols
    assert "qty_production" in cols


def test_work_order_state_machine():
    assert "ready" in WorkOrder.allowed_transitions["draft"]
    assert "in_progress" in WorkOrder.allowed_transitions["ready"]
    assert "done" in WorkOrder.allowed_transitions["in_progress"]
    assert WorkOrder.allowed_transitions["done"] == set()


def test_subcon_vendor_quality_fields():
    cols = {c.key for c in SubconVendor.__table__.columns}
    assert "variance_rate" in cols
    assert "quality_score" in cols


# ── Advanced model structure ───────────────────────────────────────────


def test_work_center_fields():
    cols = {c.key for c in WorkCenter.__table__.columns}
    assert "code" in cols
    assert "capacity" in cols
    assert "time_efficiency" in cols
    assert "cost_per_hour" in cols
    assert "oee_target" in cols


def test_routing_relationships():
    assert hasattr(Routing, "operations")
    cols = {c.key for c in RoutingOperation.__table__.columns}
    assert "sequence" in cols
    assert "work_center_id" in cols
    assert "setup_duration" in cols
    assert "default_duration" in cols


def test_mo_component_line_lot_tracking():
    cols = {c.key for c in MoComponentLine.__table__.columns}
    assert "lot_id" in cols
    assert "qty_demand" in cols
    assert "qty_done" in cols
    assert "unit_cost" in cols
    assert "total_cost" in cols


def test_mo_scrap_fields():
    cols = {c.key for c in MoScrap.__table__.columns}
    assert "mo_id" in cols
    assert "lot_id" in cols
    assert "qty" in cols
    assert "scrap_reason" in cols
    assert "scrapped_at" in cols


def test_unbuild_order_state_machine():
    assert UnbuildOrder.allowed_transitions["draft"] == {"done", "cancelled"}
    assert UnbuildOrder.allowed_transitions["done"] == set()


def test_production_shift_fields():
    cols = {c.key for c in ProductionShift.__table__.columns}
    assert "start_hour" in cols
    assert "end_hour" in cols
    constraint_names = {c.name for c in ProductionShift.__table__.constraints}
    assert "uq_shift_warehouse_code" in constraint_names


def test_work_center_oee_fields():
    cols = {c.key for c in WorkCenterOee.__table__.columns}
    assert "availability" in cols
    assert "performance" in cols
    assert "quality" in cols
    assert "oee" in cols
    assert "good_units" in cols
    constraint_names = {c.name for c in WorkCenterOee.__table__.constraints}
    assert "uq_oee_wc_date_shift" in constraint_names


def test_production_signal_fields():
    cols = {c.key for c in MoProductionSignal.__table__.columns}
    assert "avg_daily_demand" in cols
    assert "suggested_qty" in cols
    assert "wip_qty" in cols
    assert "status" in cols
    assert "converted_mo_id" in cols


def test_batch_consolidation_relationships():
    assert hasattr(BatchConsolidation, "items")
    cols = {c.key for c in BatchConsolidation.__table__.columns}
    assert "setup_saving_minutes" in cols
    assert "total_mos" in cols
    assert "window_days" in cols


# ── Service logic tests ────────────────────────────────────────────────


def test_oee_computation_full():
    result = compute_oee(
        planned_time=480,   # 8 hours
        available_time=450, # 7.5 hours (30 min downtime)
        run_time=420,       # 7 hours actual
        ideal_cycle_time=2, # 2 min per unit
        total_units=200,
        good_units=190,
    )
    assert 0 < result["availability"] <= 100
    assert 0 < result["performance"] <= 100
    assert 0 < result["quality"] <= 100
    assert 0 < result["oee"] <= 100
    # availability = 450/480*100 = 93.75
    assert result["availability"] == pytest.approx(93.75, rel=0.01)
    # quality = 190/200*100 = 95
    assert result["quality"] == pytest.approx(95.0, rel=0.01)


def test_oee_zero_planned_time():
    result = compute_oee(0, 0, 0, 1.0, 0, 0)
    assert result["oee"] == 0.0
    assert result["availability"] == 0.0


def test_oee_performance_capped_at_100():
    # ideal_cycle_time very small → would produce >100% performance
    result = compute_oee(100, 100, 100, 0.01, 1000, 1000)
    assert result["performance"] <= 100.0
