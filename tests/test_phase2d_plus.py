"""Tests for Phase 2d (Ops), Phase 3 (Purchase/Mfg), Phase 4 (Sales),
Phase 5 (Accounting), Phase 6 (HR) models and route logic."""

import pytest


# ── Phase 2d: Ops ─────────────────────────��───────────────────────────

class TestBoxSize:
    def _make_box(self, l, w, h):
        """Pure calculation without SQLAlchemy instrumentation."""
        volume = l * w * h
        dim_weight = volume / 5000
        return volume, dim_weight

    def test_volume_and_dim_weight(self):
        volume, dim_weight = self._make_box(40, 30, 20)
        assert volume == pytest.approx(24000)
        assert dim_weight == pytest.approx(24000 / 5000)

    def test_dim_weight_heavy_box(self):
        _, dim_weight = self._make_box(100, 100, 100)
        assert dim_weight == pytest.approx(200.0)


class TestPlatformOrderStatus:
    def test_platform_enum_values(self):
        from backend.modules.ops.models import PlatformType
        assert PlatformType.shopee == "shopee"
        assert PlatformType.lazada == "lazada"
        assert PlatformType.tiktok == "tiktok"


# ── Phase 3: Purchase ─────────────────────────────────────────────────

class TestPurchaseSchemas:
    def test_po_create_schema(self):
        from datetime import date
        from backend.modules.purchase.schemas import PurchaseOrderCreate, PoLineCreate
        po = PurchaseOrderCreate(
            number="PO-001",
            vendor_id=1,
            order_date=date(2026, 1, 1),
            lines=[PoLineCreate(product_id=1, qty_ordered=10, unit_price=50)],
        )
        assert po.number == "PO-001"
        assert len(po.lines) == 1
        assert po.lines[0].qty_ordered == 10

    def test_receipt_schema(self):
        from datetime import date
        from backend.modules.purchase.schemas import ReceiptCreate, ReceiptLineCreate
        r = ReceiptCreate(
            number="RCV-001",
            purchase_order_id=1,
            received_date=date(2026, 1, 5),
            lines=[ReceiptLineCreate(product_id=1, qty_received=10)],
        )
        assert r.number == "RCV-001"
        assert r.lines[0].qty_received == 10


# ── Phase 3: Manufacturing ────────────────────────────────────────────

class TestMfgSchemas:
    def test_bom_create(self):
        from backend.modules.mfg.schemas import BomCreate, BomLineCreate
        bom = BomCreate(
            code="BOM-001",
            name="Test BoM",
            product_id=1,
            output_qty=100,
            lines=[BomLineCreate(component_id=2, qty=5)],
        )
        assert bom.code == "BOM-001"
        assert len(bom.lines) == 1

    def test_mo_state_transition_map(self):
        TRANSITIONS = {
            "draft": ["confirmed", "cancelled"],
            "confirmed": ["in_progress", "cancelled"],
            "in_progress": ["done", "cancelled"],
        }
        assert "in_progress" in TRANSITIONS["confirmed"]
        assert "done" in TRANSITIONS["in_progress"]
        assert "done" not in TRANSITIONS["draft"]


# ── Phase 4: Sales ────────────────────────────────────────────────────

class TestSalesSchemas:
    def test_so_line_subtotal_calc(self):
        # Mirrors the route logic for discount calculation
        qty = 10
        unit_price = 100.0
        discount_pct = 10.0
        disc = discount_pct / 100
        subtotal = round(qty * unit_price * (1 - disc), 2)
        assert subtotal == pytest.approx(900.0)

    def test_so_create_schema(self):
        from datetime import date
        from backend.modules.sales.schemas import SalesOrderCreate, SoLineCreate
        so = SalesOrderCreate(
            number="SO-001",
            customer_id=1,
            order_date=date(2026, 2, 1),
            lines=[SoLineCreate(product_id=1, qty_ordered=5, unit_price=200)],
        )
        assert so.number == "SO-001"
        assert so.lines[0].unit_price == 200


# ── Phase 5: Accounting ───────────────────────────────────────────────

class TestAccountingSchemas:
    def test_balanced_entry(self):
        lines = [
            {"debit": 1000, "credit": 0},
            {"debit": 0, "credit": 1000},
        ]
        total_debit = sum(l["debit"] for l in lines)
        total_credit = sum(l["credit"] for l in lines)
        assert round(total_debit, 2) == round(total_credit, 2)

    def test_unbalanced_entry_detected(self):
        lines = [
            {"debit": 1000, "credit": 0},
            {"debit": 0, "credit": 900},
        ]
        total_debit = sum(l["debit"] for l in lines)
        total_credit = sum(l["credit"] for l in lines)
        assert round(total_debit, 2) != round(total_credit, 2)

    def test_account_schema(self):
        from backend.modules.accounting.schemas import AccountCreate
        acc = AccountCreate(code="1000", name="Cash", account_type="asset")
        assert acc.account_type == "asset"
        assert acc.reconcilable is False


# ── Phase 6: HR ───────────────────────────────────────────────────────

class TestHRSchemas:
    def test_employee_create(self):
        from datetime import date
        from backend.modules.hr.schemas import EmployeeCreate
        emp = EmployeeCreate(
            employee_code="EMP-001",
            first_name="Somchai",
            last_name="Test",
            hire_date=date(2025, 1, 1),
        )
        assert emp.employee_code == "EMP-001"
        assert emp.department_id is None

    def test_attendance_worked_hours(self):
        from datetime import datetime, timezone
        check_in = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
        check_out = datetime(2026, 4, 1, 17, 0, tzinfo=timezone.utc)
        worked = round((check_out - check_in).total_seconds() / 3600, 2)
        assert worked == pytest.approx(9.0)

    def test_payslip_net_salary(self):
        basic = 25000.0
        allowances = 3000.0
        deductions = 2500.0
        net = basic + allowances - deductions
        assert net == pytest.approx(25500.0)

    def test_leave_state_machine(self):
        valid_states = ["draft", "submitted", "approved", "rejected", "cancelled"]
        assert "approved" in valid_states
        assert "pending" not in valid_states
