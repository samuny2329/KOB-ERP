"""HTTP routes for the purchase module."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.purchase.models import PurchaseOrder, PoLine, Receipt, ReceiptLine, Vendor
from backend.modules.purchase.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    ReceiptCreate,
    ReceiptRead,
    VendorCreate,
    VendorRead,
)

router = APIRouter(prefix="/purchase", tags=["purchase"])


# ── Vendors ───────────────────────────────────────────────────────────


@router.get("/vendors", response_model=list[VendorRead])
async def list_vendors(session: SessionDep, _user: CurrentUser) -> list[Vendor]:
    rows = (
        await session.execute(
            select(Vendor).where(Vendor.deleted_at.is_(None)).order_by(Vendor.code)
        )
    ).scalars().all()
    return list(rows)


@router.post("/vendors", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(body: VendorCreate, session: SessionDep, _user: CurrentUser) -> Vendor:
    vendor = Vendor(**body.model_dump())
    session.add(vendor)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "vendor code already exists") from exc
    return vendor


@router.get("/vendors/{vendor_id}", response_model=VendorRead)
async def get_vendor(vendor_id: int, session: SessionDep, _user: CurrentUser) -> Vendor:
    v = await session.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vendor not found")
    return v


# ── Purchase orders ───────────────────────────────────────────────────


@router.get("/orders", response_model=list[PurchaseOrderRead])
async def list_purchase_orders(
    session: SessionDep, _user: CurrentUser, state: str | None = None
) -> list[PurchaseOrder]:
    stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.deleted_at.is_(None))
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.created_at.desc())
    )
    if state:
        stmt = stmt.where(PurchaseOrder.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    body: PurchaseOrderCreate, session: SessionDep, _user: CurrentUser
) -> PurchaseOrder:
    data = body.model_dump(exclude={"lines"})
    po = PurchaseOrder(**data)
    session.add(po)
    await session.flush()
    subtotal = 0.0
    total_tax = 0.0
    for line_data in body.lines:
        line = PoLine(order_id=po.id, **line_data.model_dump())
        line.subtotal = float(line.qty_ordered) * float(line.unit_price)
        line.tax_amount = round(line.subtotal * float(line.tax_rate) / 100, 2)
        line.total = line.subtotal + line.tax_amount
        subtotal += line.subtotal
        total_tax += line.tax_amount
        session.add(line)
    po.subtotal = subtotal
    po.tax_amount = total_tax
    po.total_amount = subtotal + total_tax
    await session.flush()
    await session.refresh(po, ["lines"])
    return po


@router.post("/orders/{po_id}/confirm", response_model=PurchaseOrderRead)
async def confirm_po(po_id: int, session: SessionDep, _user: CurrentUser) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    if po.state != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot confirm PO in state {po.state!r}")
    po.state = "confirmed"
    po.confirmed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(po, ["lines"])
    return po


@router.post("/orders/{po_id}/cancel", response_model=PurchaseOrderRead)
async def cancel_po(po_id: int, session: SessionDep, _user: CurrentUser) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    if po.state in ("received", "closed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot cancel PO in state {po.state!r}")
    po.state = "cancelled"
    await session.flush()
    await session.refresh(po, ["lines"])
    return po


# ── Receipts ──────────────────────────────────────────────────────────


@router.get("/receipts", response_model=list[ReceiptRead])
async def list_receipts(
    session: SessionDep, _user: CurrentUser, po_id: int | None = None
) -> list[Receipt]:
    stmt = (
        select(Receipt)
        .where(Receipt.deleted_at.is_(None))
        .options(selectinload(Receipt.lines))
        .order_by(Receipt.created_at.desc())
    )
    if po_id:
        stmt = stmt.where(Receipt.purchase_order_id == po_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    body: ReceiptCreate, session: SessionDep, _user: CurrentUser
) -> Receipt:
    data = body.model_dump(exclude={"lines"})
    receipt = Receipt(**data)
    session.add(receipt)
    await session.flush()
    for ld in body.lines:
        session.add(ReceiptLine(receipt_id=receipt.id, **ld.model_dump()))
    await session.flush()
    await session.refresh(receipt, ["lines"])
    return receipt


@router.post("/receipts/{receipt_id}/validate", response_model=ReceiptRead)
async def validate_receipt(
    receipt_id: int, session: SessionDep, _user: CurrentUser
) -> Receipt:
    receipt = await session.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "receipt not found")
    if receipt.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"cannot validate receipt in state {receipt.state!r}"
        )
    receipt.state = "done"
    receipt.validated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(receipt, ["lines"])
    return receipt
