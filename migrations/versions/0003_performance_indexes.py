"""Performance indexes for all modules.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-30
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # inventory
    op.create_index("ix_stock_quant_product", "stock_quant", ["product_id"], schema="inventory")
    op.create_index("ix_transfer_state", "transfer", ["state"], schema="inventory")
    op.create_index("ix_transfer_created", "transfer", ["created_at"], schema="inventory")

    # outbound
    op.create_index("ix_order_state", "order", ["state"], schema="outbound")
    op.create_index("ix_order_created", "order", ["created_at"], schema="outbound")

    # ops
    op.create_index("ix_platform_order_platform", "platform_order", ["platform"], schema="ops")
    op.create_index("ix_platform_order_status", "platform_order", ["status"], schema="ops")
    op.create_index("ix_daily_report_date", "daily_report", ["report_date"], schema="ops")
    op.create_index("ix_worker_kpi_date", "worker_kpi", ["kpi_date"], schema="ops")

    # purchase
    op.create_index("ix_po_state", "purchase_order", ["state"], schema="purchase")
    op.create_index("ix_po_vendor", "purchase_order", ["vendor_id"], schema="purchase")

    # mfg
    op.create_index("ix_mo_state", "manufacturing_order", ["state"], schema="mfg")

    # sales
    op.create_index("ix_so_state", "sales_order", ["state"], schema="sales")
    op.create_index("ix_so_customer", "sales_order", ["customer_id"], schema="sales")
    op.create_index("ix_delivery_state", "delivery", ["state"], schema="sales")

    # accounting
    op.create_index("ix_je_state", "journal_entry", ["state"], schema="accounting")
    op.create_index("ix_je_date", "journal_entry", ["entry_date"], schema="accounting")
    op.create_index("ix_account_type", "account", ["account_type"], schema="accounting")

    # hr
    op.create_index("ix_employee_dept", "employee", ["department_id"], schema="hr")
    op.create_index("ix_attendance_emp", "attendance", ["employee_id"], schema="hr")
    op.create_index("ix_leave_emp", "leave", ["employee_id"], schema="hr")
    op.create_index("ix_leave_state", "leave", ["state"], schema="hr")
    op.create_index("ix_payslip_emp", "payslip", ["employee_id"], schema="hr")

    # core audit
    op.create_index("ix_activity_log_ref", "activity_log", ["ref_model", "ref_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_activity_log_ref", "activity_log", schema="core")
    op.drop_index("ix_payslip_emp", "payslip", schema="hr")
    op.drop_index("ix_leave_state", "leave", schema="hr")
    op.drop_index("ix_leave_emp", "leave", schema="hr")
    op.drop_index("ix_attendance_emp", "attendance", schema="hr")
    op.drop_index("ix_employee_dept", "employee", schema="hr")
    op.drop_index("ix_account_type", "account", schema="accounting")
    op.drop_index("ix_je_date", "journal_entry", schema="accounting")
    op.drop_index("ix_je_state", "journal_entry", schema="accounting")
    op.drop_index("ix_delivery_state", "delivery", schema="sales")
    op.drop_index("ix_so_customer", "sales_order", schema="sales")
    op.drop_index("ix_so_state", "sales_order", schema="sales")
    op.drop_index("ix_mo_state", "manufacturing_order", schema="mfg")
    op.drop_index("ix_po_vendor", "purchase_order", schema="purchase")
    op.drop_index("ix_po_state", "purchase_order", schema="purchase")
    op.drop_index("ix_worker_kpi_date", "worker_kpi", schema="ops")
    op.drop_index("ix_daily_report_date", "daily_report", schema="ops")
    op.drop_index("ix_platform_order_status", "platform_order", schema="ops")
    op.drop_index("ix_platform_order_platform", "platform_order", schema="ops")
    op.drop_index("ix_order_created", "order", schema="outbound")
    op.drop_index("ix_order_state", "order", schema="outbound")
    op.drop_index("ix_transfer_created", "transfer", schema="inventory")
    op.drop_index("ix_transfer_state", "transfer", schema="inventory")
    op.drop_index("ix_stock_quant_product", "stock_quant", schema="inventory")
