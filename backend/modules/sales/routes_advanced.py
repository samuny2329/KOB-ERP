"""Advanced sales routes — teams, pricelists, RMA, quotation templates, e-Tax, IC-SO."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import SessionDep
from backend.modules.sales.models import Customer, SalesOrder, SoLine
from backend.modules.sales.models_advanced import (
    EtaxInvoiceRef,
    IntercompanySalesOrder,
    PlatformFeeRule,
    QuotationTemplate,
    QuotationTemplateLine,
    RmaOrder,
    SalesTeam,
    SalesPricelist,
    SalesPriceRule,
    SoMarginLine,
)
from backend.modules.sales.schemas_advanced import (
    ApplyPricelistPayload,
    BestPriceResult,
    EtaxInvoiceRefCreate,
    EtaxInvoiceRefRead,
    IntercompanySalesOrderCreate,
    IntercompanySalesOrderRead,
    MarginBreakdown,
    PlatformFeeRuleCreate,
    PlatformFeeRuleRead,
    QuotationTemplateCreate,
    QuotationTemplateRead,
    RmaOrderCreate,
    RmaOrderRead,
    SalesPriceRuleCreate,
    SalesPriceRuleRead,
    SalesPricelistCreate,
    SalesPricelistRead,
    SalesTeamCreate,
    SalesTeamRead,
    SoMarginLineRead,
)
from backend.modules.sales.service import (
    apply_pricelist,
    confirm_sales_order,
    create_intercompany_so,
    create_rma,
    get_active_platform_fee,
    send_quotation,
)

router = APIRouter(prefix="/sales", tags=["sales-advanced"])


# ── Sales Teams ────────────────────────────────────────────────────────


@router.post("/teams", response_model=SalesTeamRead, status_code=status.HTTP_201_CREATED)
async def create_sales_team(payload: SalesTeamCreate, session: SessionDep):
    team = SalesTeam(**payload.model_dump())
    session.add(team)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "team code already exists")
    return team


@router.get("/teams", response_model=list[SalesTeamRead])
async def list_sales_teams(session: SessionDep, active_only: bool = True):
    stmt = select(SalesTeam).where(SalesTeam.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(SalesTeam.active.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Pricelists ─────────────────────────────────────────────────────────


@router.post("/pricelist", response_model=SalesPricelistRead, status_code=status.HTTP_201_CREATED)
async def create_pricelist(payload: SalesPricelistCreate, session: SessionDep):
    pl = SalesPricelist(**payload.model_dump())
    session.add(pl)
    await session.flush()
    return pl


@router.get("/pricelist", response_model=list[SalesPricelistRead])
async def list_pricelists(session: SessionDep, active_only: bool = True):
    stmt = select(SalesPricelist).where(SalesPricelist.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(SalesPricelist.active.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/pricelist/rules", response_model=SalesPriceRuleRead, status_code=status.HTTP_201_CREATED)
async def create_price_rule(payload: SalesPriceRuleCreate, session: SessionDep):
    rule = SalesPriceRule(**payload.model_dump())
    session.add(rule)
    await session.flush()
    return rule


@router.get("/pricelist/rules", response_model=list[SalesPriceRuleRead])
async def list_price_rules(session: SessionDep, pricelist_id: int | None = None):
    stmt = select(SalesPriceRule).where(SalesPriceRule.deleted_at.is_(None))
    if pricelist_id:
        stmt = stmt.where(SalesPriceRule.pricelist_id == pricelist_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/pricelist/best-price", response_model=BestPriceResult)
async def get_best_price(
    session: SessionDep,
    product_id: int = Query(...),
    qty: float = Query(...),
    pricelist_id: int | None = Query(None),
):
    from backend.modules.sales.service import _find_best_rule
    today = datetime.now(UTC).date()
    if pricelist_id:
        pl = await session.get(SalesPricelist, pricelist_id, options=[selectinload(SalesPricelist.rules)])
        if pl:
            rule = _find_best_rule(pl.rules, product_id, qty, today)
            if rule:
                return BestPriceResult(product_id=product_id, qty=qty, unit_price=float(rule.price), pricelist_id=pricelist_id, rule_id=rule.id)
    return BestPriceResult(product_id=product_id, qty=qty, unit_price=0.0)


# ── RMA ────────────────────────────────────────────────────────────────


@router.post("/rma", response_model=RmaOrderRead, status_code=status.HTTP_201_CREATED)
async def create_rma_endpoint(payload: RmaOrderCreate, session: SessionDep):
    so = await session.get(SalesOrder, payload.so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    rma = await create_rma(session, so, payload.number, [l.model_dump() for l in payload.lines], payload.reason)
    return rma


@router.get("/rma", response_model=list[RmaOrderRead])
async def list_rma(session: SessionDep, so_id: int | None = None):
    stmt = select(RmaOrder).where(RmaOrder.deleted_at.is_(None)).options(selectinload(RmaOrder.lines))
    if so_id:
        stmt = stmt.where(RmaOrder.so_id == so_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/rma/{rma_id}/confirm", response_model=RmaOrderRead)
async def confirm_rma(rma_id: int, session: SessionDep):
    rma = await session.get(RmaOrder, rma_id, options=[selectinload(RmaOrder.lines)])
    if not rma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RMA not found")
    from backend.core.workflow import WorkflowError
    try:
        rma.transition("confirmed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    rma.confirmed_at = datetime.now(UTC)
    await session.flush()
    return rma


@router.post("/rma/{rma_id}/receive", response_model=RmaOrderRead)
async def receive_rma(rma_id: int, session: SessionDep):
    rma = await session.get(RmaOrder, rma_id, options=[selectinload(RmaOrder.lines)])
    if not rma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RMA not found")
    from backend.core.workflow import WorkflowError
    try:
        rma.transition("received")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    rma.received_at = datetime.now(UTC)
    await session.flush()
    return rma


@router.post("/rma/{rma_id}/done", response_model=RmaOrderRead)
async def complete_rma(rma_id: int, session: SessionDep):
    rma = await session.get(RmaOrder, rma_id, options=[selectinload(RmaOrder.lines)])
    if not rma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RMA not found")
    from backend.core.workflow import WorkflowError
    try:
        rma.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    rma.done_at = datetime.now(UTC)
    await session.flush()
    return rma


@router.post("/rma/{rma_id}/cancel", response_model=RmaOrderRead)
async def cancel_rma(rma_id: int, session: SessionDep):
    rma = await session.get(RmaOrder, rma_id, options=[selectinload(RmaOrder.lines)])
    if not rma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RMA not found")
    from backend.core.workflow import WorkflowError
    try:
        rma.transition("cancelled")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return rma


# ── Quotation Templates ────────────────────────────────────────────────


@router.post("/quotation-templates", response_model=QuotationTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_quotation_template(payload: QuotationTemplateCreate, session: SessionDep):
    tmpl = QuotationTemplate(name=payload.name, active=payload.active)
    session.add(tmpl)
    await session.flush()
    for line in payload.lines:
        session.add(QuotationTemplateLine(template_id=tmpl.id, **line.model_dump()))
    await session.flush()
    await session.refresh(tmpl, ["lines"])
    return tmpl


@router.get("/quotation-templates", response_model=list[QuotationTemplateRead])
async def list_quotation_templates(session: SessionDep):
    stmt = select(QuotationTemplate).where(QuotationTemplate.deleted_at.is_(None)).options(
        selectinload(QuotationTemplate.lines)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


# ── SO Actions ─────────────────────────────────────────────────────────


@router.post("/orders/{so_id}/send")
async def send_so(so_id: int, session: SessionDep):
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    await send_quotation(session, so)
    return {"id": so.id, "state": so.state, "sent_at": so.sent_at}


@router.post("/orders/{so_id}/confirm")
async def confirm_so(so_id: int, session: SessionDep):
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    await confirm_sales_order(session, so)
    return {"id": so.id, "state": so.state, "confirmed_at": so.confirmed_at}


@router.post("/orders/{so_id}/apply-pricelist")
async def apply_pricelist_to_so(so_id: int, payload: ApplyPricelistPayload, session: SessionDep):
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    await apply_pricelist(session, so, payload.pricelist_id)
    return {"id": so.id, "pricelist_id": so.pricelist_id}


@router.post("/orders/{so_id}/intercompany", response_model=IntercompanySalesOrderRead)
async def create_ic_so(so_id: int, payload: IntercompanySalesOrderCreate, session: SessionDep):
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    if not so.company_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SO must have company_id set to create IC-SO")
    ic = await create_intercompany_so(session, so, payload.to_company_id, so.company_id)
    return ic


@router.get("/orders/{so_id}/margins", response_model=list[SoMarginLineRead])
async def get_so_margins(so_id: int, session: SessionDep):
    lines_result = await session.execute(
        select(SoLine).where(SoLine.order_id == so_id)
    )
    so_line_ids = [l.id for l in lines_result.scalars().all()]
    if not so_line_ids:
        return []
    margins_result = await session.execute(
        select(SoMarginLine).where(SoMarginLine.so_line_id.in_(so_line_ids))
    )
    return margins_result.scalars().all()


# ── Platform Fee Rules ─────────────────────────────────────────────────


@router.post("/platform-fee-rules", response_model=PlatformFeeRuleRead, status_code=status.HTTP_201_CREATED)
async def create_platform_fee_rule(payload: PlatformFeeRuleCreate, session: SessionDep):
    rule = PlatformFeeRule(**payload.model_dump())
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "fee rule already exists for this platform/company/date")
    return rule


@router.get("/platform-fee-rules", response_model=list[PlatformFeeRuleRead])
async def list_platform_fee_rules(session: SessionDep, platform: str | None = None):
    stmt = select(PlatformFeeRule).where(PlatformFeeRule.deleted_at.is_(None))
    if platform:
        stmt = stmt.where(PlatformFeeRule.platform == platform)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── e-Tax Invoice References ────────────────────────────────────────────


@router.post("/etax-invoices", response_model=EtaxInvoiceRefRead, status_code=status.HTTP_201_CREATED)
async def create_etax_invoice(payload: EtaxInvoiceRefCreate, session: SessionDep):
    ref = EtaxInvoiceRef(**payload.model_dump())
    session.add(ref)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "etax_number already used in this company")
    return ref


@router.get("/etax-invoices", response_model=list[EtaxInvoiceRefRead])
async def list_etax_invoices(session: SessionDep, so_id: int | None = None):
    stmt = select(EtaxInvoiceRef).where(EtaxInvoiceRef.deleted_at.is_(None))
    if so_id:
        stmt = stmt.where(EtaxInvoiceRef.so_id == so_id)
    result = await session.execute(stmt)
    return result.scalars().all()
