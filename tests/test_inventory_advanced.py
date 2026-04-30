"""Tests for advanced inventory models and service logic (Odoo 19 parity)."""

import pytest

from backend.modules.inventory.models_advanced import (
    LandedCost,
    LandedCostLine,
    LandedCostTransfer,
    Package,
    PackageType,
    PutawayRule,
    ReorderRule,
    ScrapOrder,
    StockValuationLayer,
)


# ── Model structure tests ──────────────────────────────────────────────


def test_scrap_state_machine():
    assert ScrapOrder.allowed_transitions["draft"] == {"done", "cancelled"}
    assert ScrapOrder.allowed_transitions["done"] == set()
    assert ScrapOrder.allowed_transitions["cancelled"] == set()


def test_landed_cost_state_machine():
    assert LandedCost.allowed_transitions["draft"] == {"posted", "cancelled"}
    assert LandedCost.allowed_transitions["posted"] == set()
    assert LandedCost.allowed_transitions["cancelled"] == set()


def test_putaway_rule_model_fields():
    cols = {c.key for c in PutawayRule.__table__.columns}
    assert "location_id" in cols
    assert "location_dest_id" in cols
    assert "product_id" in cols
    assert "product_category_id" in cols
    assert "sequence" in cols
    assert "active" in cols


def test_reorder_rule_unique_constraint():
    constraint_names = {c.name for c in ReorderRule.__table__.constraints}
    assert "uq_reorder_product_location" in constraint_names


def test_stock_valuation_layer_fields():
    cols = {c.key for c in StockValuationLayer.__table__.columns}
    assert "product_id" in cols
    assert "quantity" in cols
    assert "unit_cost" in cols
    assert "value" in cols
    assert "remaining_qty" in cols
    assert "remaining_value" in cols
    assert "landed_cost_id" in cols


def test_package_self_reference():
    # parent_id FK references inventory.package (self-referential)
    fk_targets = {
        fk.target_fullname
        for c in Package.__table__.columns
        for fk in c.foreign_keys
    }
    assert any("package" in t for t in fk_targets)


def test_package_type_fields():
    cols = {c.key for c in PackageType.__table__.columns}
    assert "name" in cols
    assert "max_weight_kg" in cols
    assert "barcode" in cols
    assert "active" in cols


def test_landed_cost_line_relationship():
    assert hasattr(LandedCost, "lines")
    assert hasattr(LandedCost, "transfer_links")
    assert hasattr(LandedCostLine, "landed_cost")
    assert hasattr(LandedCostTransfer, "landed_cost")


def test_reorder_rule_fields():
    cols = {c.key for c in ReorderRule.__table__.columns}
    assert "qty_min" in cols
    assert "qty_max" in cols
    assert "qty_multiple" in cols
    assert "lead_days" in cols
    assert "last_triggered_at" in cols
    assert "last_qty_ordered" in cols


# ── Schema tests ───────────────────────────────────────────────────────


def test_scrap_order_schema_validation():
    from backend.modules.inventory.schemas_advanced import ScrapOrderCreate

    with pytest.raises(Exception):
        ScrapOrderCreate(
            product_id=1,
            uom_id=1,
            scrap_qty=-1,  # must be > 0
            source_location_id=1,
            scrap_location_id=2,
        )


def test_reorder_rule_schema_validation():
    from backend.modules.inventory.schemas_advanced import ReorderRuleCreate

    rule = ReorderRuleCreate(
        product_id=1,
        location_id=2,
        warehouse_id=3,
        qty_min=10.0,
        qty_max=100.0,
        qty_multiple=5.0,
        lead_days=3,
    )
    assert rule.qty_multiple == 5.0
    assert rule.lead_days == 3


def test_putaway_rule_schema():
    from backend.modules.inventory.schemas_advanced import PutawayRuleCreate

    rule = PutawayRuleCreate(location_id=1, location_dest_id=2, sequence=10)
    assert rule.active is True
    assert rule.product_id is None
    assert rule.product_category_id is None


def test_return_create_schema():
    from backend.modules.inventory.schemas_advanced import ReturnCreate, ReturnLineItem

    r = ReturnCreate(lines=[ReturnLineItem(transfer_line_id=5, quantity=3.0)])
    assert len(r.lines) == 1
    assert r.lines[0].quantity == 3.0


def test_landed_cost_schema_with_lines():
    from datetime import date

    from backend.modules.inventory.schemas_advanced import LandedCostCreate, LandedCostLineCreate

    lc = LandedCostCreate(
        name="LC/001",
        date=date.today(),
        lines=[LandedCostLineCreate(name="Freight", amount=500.0)],
        transfer_ids=[1, 2],
    )
    assert lc.split_method == "by_quantity"
    assert len(lc.lines) == 1
    assert lc.lines[0].amount == 500.0
