"""Advanced purchase routes — payment terms, pricelist, vendor docs, WHT, budget, signals."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.purchase.models import PurchaseOrder, Vendor
from backend.modules.purchase.models_advanced import (
    DemandSignal,
    PaymentTerm,
    PaymentTermLine,
    PoConsolidationProposal,
    ProcurementBudget,
    SupplierPricelist,
    VendorDocument,
    VendorPerformance,
    WhtCertificate,
)
from backend.modules.purchase.schemas_advanced import (
    DemandSignalRead,
    PaymentTermCreate,
    PaymentTermRead,
    PoApproveBody,
    PoConsolidationProposalRead,
    PoRejectBody,
    ProcurementBudgetCreate,
    ProcurementBudgetRead,
    SupplierPricelistCreate,
    SupplierPricelistRead,
    VendorDocumentCreate,
    VendorDocumentRead,
    VendorPerformanceRead,
    WhtCertificateCreate,
    WhtCertificateRead,
)
from backend.modules.purchase.schemas import PurchaseOrderRead
from backend.modules.purchase.service import (
    check_and_apply_budget,
    compute_demand_signals,
    confirm_purchase_order,
    generate_wht_certificate,
    get_best_supplier_price,
    propose_consolidation,
    recompute_vendor_performance,
)

router = APIRouter(prefix="/purchase", tags=["purchase-advanced"])


# ── Payment Terms ──────────────────────────────────────────────────────


@router.post("/payment-terms", response_model=PaymentTermRead, status_code=status.HTTP_201_CREATED)
async def create_payment_term(
    body: PaymentTermCreate, session: SessionDep, _user: CurrentUser
) -> PaymentTerm:
    pt = PaymentTerm(name=body.name, note=body.note, active=body.active)
    session.add(pt)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "payment term name already exists") from exc
    for line_data in body.lines:
        session.add(PaymentTermLine(payment_term_id=pt.id, **line_data.model_dump()))
    await session.flush()
    await session.refresh(pt, ["lines"])
    return pt


@router.get("/payment-terms", response_model=list[PaymentTermRead])
async def list_payment_terms(session: SessionDep, _user: CurrentUser) -> list[PaymentTerm]:
    stmt = (
        select(PaymentTerm)
        .where(PaymentTerm.deleted_at.is_(None), PaymentTerm.active.is_(True))
        .options(selectinload(PaymentTerm.lines))
        .order_by(PaymentTerm.name)
    )
    return list((await session.execute(stmt)).scalars().all())


# ── Supplier Pricelist ─────────────────────────────────────────────────


@router.post("/pricelist", response_model=SupplierPricelistRead, status_code=status.HTTP_201_CREATED)
async def create_pricelist_entry(
    body: SupplierPricelistCreate, session: SessionDep, _user: CurrentUser
) -> SupplierPricelist:
    entry = SupplierPricelist(**body.model_dump())
    session.add(entry)
    await session.flush()
    return entry


@router.get("/pricelist", response_model=list[SupplierPricelistRead])
async def list_pricelist(
    session: SessionDep,
    _user: CurrentUser,
    vendor_id: int | None = None,
    product_id: int | None = None,
    active_only: bool = True,
) -> list[SupplierPricelist]:
    stmt = select(SupplierPricelist).where(SupplierPricelist.deleted_at.is_(None))
    if vendor_id is not None:
        stmt = stmt.where(SupplierPricelist.vendor_id == vendor_id)
    if product_id is not None:
        stmt = stmt.where(SupplierPricelist.product_id == product_id)
    if active_only:
        stmt = stmt.where(SupplierPricelist.active.is_(True))
    return list((await session.execute(stmt.order_by(SupplierPricelist.min_qty))).scalars().all())


@router.get("/pricelist/best-price", response_model=SupplierPricelistRead | None)
async def best_price(
    vendor_id: int,
    product_id: int,
    qty: float,
    session: SessionDep,
    _user: CurrentUser,
) -> SupplierPricelist | None:
    return await get_best_supplier_price(session, vendor_id, product_id, qty)


# ── Vendor Documents ───────────────────────────────────────────────────


@router.post("/vendor-documents", response_model=VendorDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_document(
    body: VendorDocumentCreate, session: SessionDep, _user: CurrentUser
) -> VendorDocument:
    doc = VendorDocument(**body.model_dump())
    session.add(doc)
    await session.flush()
    return doc


@router.get("/vendor-documents", response_model=list[VendorDocumentRead])
async def list_vendor_documents(
    session: SessionDep,
    _user: CurrentUser,
    vendor_id: int | None = None,
    expiring_within_days: int | None = None,
) -> list[VendorDocument]:
    stmt = select(VendorDocument).where(
        VendorDocument.deleted_at.is_(None), VendorDocument.active.is_(True)
    )
    if vendor_id is not None:
        stmt = stmt.where(VendorDocument.vendor_id == vendor_id)
    if expiring_within_days is not None:
        threshold = date.today() + __import__("datetime").timedelta(days=expiring_within_days)
        stmt = stmt.where(
            VendorDocument.expiry_date.is_not(None),
            VendorDocument.expiry_date <= threshold,
        )
    return list((await session.execute(stmt.order_by(VendorDocument.expiry_date))).scalars().all())


@router.delete("/vendor-documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_document(
    doc_id: int, session: SessionDep, _user: CurrentUser
) -> None:
    doc = await session.get(VendorDocument, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    await session.delete(doc)
    await session.flush()


# ── Vendor Performance ─────────────────────────────────────────────────


@router.get("/vendors/{vendor_id}/performance", response_model=list[VendorPerformanceRead])
async def get_vendor_performance(
    vendor_id: int,
    session: SessionDep,
    _user: CurrentUser,
    limit: int = 12,
) -> list[VendorPerformance]:
    stmt = (
        select(VendorPerformance)
        .where(VendorPerformance.vendor_id == vendor_id)
        .order_by(VendorPerformance.period_year.desc(), VendorPerformance.period_month.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/vendors/{vendor_id}/performance/recompute", response_model=VendorPerformanceRead)
async def recompute_performance(
    vendor_id: int, session: SessionDep, _user: CurrentUser
) -> VendorPerformance:
    today = datetime.now(UTC)
    return await recompute_vendor_performance(session, vendor_id, today.year, today.month)


# ── WHT Certificates ───────────────────────────────────────────────────


@router.post("/wht-certificates", response_model=WhtCertificateRead, status_code=status.HTTP_201_CREATED)
async def create_wht_certificate(
    body: WhtCertificateCreate, session: SessionDep, _user: CurrentUser
) -> WhtCertificate:
    cert = WhtCertificate(**body.model_dump())
    session.add(cert)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "certificate number already exists") from exc
    return cert


@router.post("/orders/{po_id}/wht-certificate/auto", response_model=WhtCertificateRead)
async def auto_generate_wht(po_id: int, session: SessionDep, _user: CurrentUser) -> WhtCertificate:
    po = await session.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    return await generate_wht_certificate(session, po)


@router.get("/wht-certificates", response_model=list[WhtCertificateRead])
async def list_wht_certificates(
    session: SessionDep,
    _user: CurrentUser,
    vendor_id: int | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    submitted: bool | None = None,
) -> list[WhtCertificate]:
    stmt = select(WhtCertificate).where(WhtCertificate.deleted_at.is_(None))
    if vendor_id is not None:
        stmt = stmt.where(WhtCertificate.vendor_id == vendor_id)
    if period_year is not None:
        stmt = stmt.where(WhtCertificate.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(WhtCertificate.period_month == period_month)
    if submitted is not None:
        stmt = stmt.where(WhtCertificate.submitted == submitted)
    return list(
        (await session.execute(stmt.order_by(WhtCertificate.payment_date.desc()))).scalars().all()
    )


@router.post("/wht-certificates/{cert_id}/submit", response_model=WhtCertificateRead)
async def mark_wht_submitted(
    cert_id: int, session: SessionDep, _user: CurrentUser
) -> WhtCertificate:
    cert = await session.get(WhtCertificate, cert_id)
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "certificate not found")
    cert.submitted = True
    cert.submitted_at = datetime.now(UTC)
    await session.flush()
    return cert


# ── Procurement Budget ─────────────────────────────────────────────────


@router.post("/budgets", response_model=ProcurementBudgetRead, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: ProcurementBudgetCreate, session: SessionDep, _user: CurrentUser
) -> ProcurementBudget:
    budget = ProcurementBudget(**body.model_dump(), state="draft")
    session.add(budget)
    await session.flush()
    return budget


@router.get("/budgets", response_model=list[ProcurementBudgetRead])
async def list_budgets(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    fiscal_year: int | None = None,
) -> list[ProcurementBudget]:
    stmt = select(ProcurementBudget).where(ProcurementBudget.deleted_at.is_(None))
    if state is not None:
        stmt = stmt.where(ProcurementBudget.state == state)
    if fiscal_year is not None:
        stmt = stmt.where(ProcurementBudget.fiscal_year == fiscal_year)
    return list((await session.execute(stmt.order_by(ProcurementBudget.id.desc()))).scalars().all())


@router.post("/budgets/{budget_id}/activate", response_model=ProcurementBudgetRead)
async def activate_budget(
    budget_id: int, session: SessionDep, _user: CurrentUser
) -> ProcurementBudget:
    from backend.core.workflow import WorkflowError
    budget = await session.get(ProcurementBudget, budget_id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "budget not found")
    try:
        budget.transition("active")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return budget


# ── PO Approval Workflow ───────────────────────────────────────────────


@router.post("/orders/{po_id}/request-approval", response_model=PurchaseOrderRead)
async def request_po_approval(
    po_id: int, session: SessionDep, _user: CurrentUser
) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.lines)])
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    if po.state not in ("draft", "sent"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot request approval in state {po.state!r}")
    po.state = "waiting_approval"
    po.approval_state = "pending"
    await session.flush()
    return po


@router.post("/orders/{po_id}/approve", response_model=PurchaseOrderRead)
async def approve_po(
    po_id: int, body: PoApproveBody, session: SessionDep, _user: CurrentUser
) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.lines)])
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    if po.approval_state != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "PO is not pending approval")
    po.approval_state = "approved"
    po.approved_at = datetime.now(UTC)
    po.approver_id = _user.id
    if body.note:
        po.note_internal = (po.note_internal or "") + f"\n[Approved] {body.note}"
    return await confirm_purchase_order(session, po, auto_create_receipt=True)


@router.post("/orders/{po_id}/reject", response_model=PurchaseOrderRead)
async def reject_po(
    po_id: int, body: PoRejectBody, session: SessionDep, _user: CurrentUser
) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.lines)])
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")
    if po.approval_state != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "PO is not pending approval")
    po.approval_state = "rejected"
    po.state = "draft"
    po.note_internal = (po.note_internal or "") + f"\n[Rejected] {body.reason}"
    await session.flush()
    await session.refresh(po, ["lines"])
    return po


# ── Enhanced PO confirm (with budget check) ────────────────────────────


@router.post("/orders/{po_id}/confirm", response_model=PurchaseOrderRead)
async def confirm_po_advanced(
    po_id: int, session: SessionDep, _user: CurrentUser
) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.lines)])
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PO not found")

    # Budget check
    ok, msg = await check_and_apply_budget(session, po)
    if not ok:
        po.state = "waiting_approval"
        po.approval_state = "pending"
        await session.flush()
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Budget exceeded — PO moved to waiting_approval: {msg}",
        )

    return await confirm_purchase_order(session, po, auto_create_receipt=True)


# ── Demand Signals ─────────────────────────────────────────────────────


@router.post("/demand-signals/compute", response_model=DemandSignalRead)
async def compute_signal(
    product_id: int,
    current_on_hand: float,
    session: SessionDep,
    _user: CurrentUser,
    lookback_days: int = 30,
) -> DemandSignal:
    return await compute_demand_signals(
        session, product_id, current_on_hand, lookback_days=lookback_days
    )


@router.get("/demand-signals", response_model=list[DemandSignalRead])
async def list_demand_signals(
    session: SessionDep,
    _user: CurrentUser,
    status_filter: str | None = None,
    product_id: int | None = None,
    limit: int = 50,
) -> list[DemandSignal]:
    stmt = (
        select(DemandSignal)
        .where(DemandSignal.deleted_at.is_(None))
        .order_by(DemandSignal.computed_at.desc())
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(DemandSignal.status == status_filter)
    if product_id is not None:
        stmt = stmt.where(DemandSignal.product_id == product_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/demand-signals/{signal_id}/convert", response_model=DemandSignalRead)
async def convert_signal_to_po(
    signal_id: int, po_id: int, session: SessionDep, _user: CurrentUser
) -> DemandSignal:
    signal = await session.get(DemandSignal, signal_id)
    if signal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "demand signal not found")
    signal.status = "converted"
    signal.converted_po_id = po_id
    await session.flush()
    return signal


# ── PO Consolidation Engine ────────────────────────────────────────────


@router.post("/consolidation/propose", response_model=PoConsolidationProposalRead | None)
async def propose_po_consolidation(
    vendor_id: int,
    session: SessionDep,
    _user: CurrentUser,
    window_days: int = 7,
) -> PoConsolidationProposal | None:
    return await propose_consolidation(session, vendor_id, window_days=window_days)


@router.get("/consolidation/proposals", response_model=list[PoConsolidationProposalRead])
async def list_consolidation_proposals(
    session: SessionDep,
    _user: CurrentUser,
    vendor_id: int | None = None,
    status_filter: str | None = None,
) -> list[PoConsolidationProposal]:
    stmt = (
        select(PoConsolidationProposal)
        .where(PoConsolidationProposal.deleted_at.is_(None))
        .options(selectinload(PoConsolidationProposal.items))
        .order_by(PoConsolidationProposal.proposed_at.desc())
    )
    if vendor_id is not None:
        stmt = stmt.where(PoConsolidationProposal.vendor_id == vendor_id)
    if status_filter is not None:
        stmt = stmt.where(PoConsolidationProposal.status == status_filter)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/consolidation/proposals/{proposal_id}/accept", response_model=PoConsolidationProposalRead)
async def accept_consolidation(
    proposal_id: int, session: SessionDep, _user: CurrentUser
) -> PoConsolidationProposal:
    proposal = await session.get(
        PoConsolidationProposal, proposal_id,
        options=[selectinload(PoConsolidationProposal.items)]
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "proposal is not pending")
    proposal.status = "accepted"
    proposal.reviewed_at = datetime.now(UTC)
    proposal.reviewed_by_id = _user.id
    await session.flush()
    return proposal


@router.post("/consolidation/proposals/{proposal_id}/reject", response_model=PoConsolidationProposalRead)
async def reject_consolidation(
    proposal_id: int, session: SessionDep, _user: CurrentUser
) -> PoConsolidationProposal:
    proposal = await session.get(
        PoConsolidationProposal, proposal_id,
        options=[selectinload(PoConsolidationProposal.items)]
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proposal not found")
    proposal.status = "rejected"
    proposal.reviewed_at = datetime.now(UTC)
    proposal.reviewed_by_id = _user.id
    await session.flush()
    return proposal
