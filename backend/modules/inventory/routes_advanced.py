"""Advanced inventory routes — packages, putaway, reorder, scrap, landed costs."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.inventory.models import Transfer
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
from backend.modules.inventory.schemas_advanced import (
    LandedCostCreate,
    LandedCostRead,
    PackageCreate,
    PackageRead,
    PackageTypeCreate,
    PackageTypeRead,
    PutawayRuleCreate,
    PutawayRuleRead,
    ReorderRuleCreate,
    ReorderRuleRead,
    ReorderRuleUpdate,
    ReturnCreate,
    ScrapOrderCreate,
    ScrapOrderRead,
    StockValuationLayerRead,
)
from backend.modules.inventory.schemas import TransferRead
from backend.modules.inventory.service import (
    create_backorder,
    create_return_transfer,
    post_landed_cost,
    validate_scrap,
)

router = APIRouter(prefix="/inventory", tags=["inventory-advanced"])


# ── Package Types ──────────────────────────────────────────────────────


@router.post("/package-types", response_model=PackageTypeRead, status_code=status.HTTP_201_CREATED)
async def create_package_type(
    body: PackageTypeCreate, session: SessionDep, _user: CurrentUser
) -> PackageType:
    pt = PackageType(**body.model_dump())
    session.add(pt)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "package type name or barcode already exists") from exc
    return pt


@router.get("/package-types", response_model=list[PackageTypeRead])
async def list_package_types(
    session: SessionDep, _user: CurrentUser, active_only: bool = True
) -> list[PackageType]:
    stmt = select(PackageType).where(PackageType.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(PackageType.active.is_(True))
    return list((await session.execute(stmt.order_by(PackageType.name))).scalars().all())


# ── Packages ───────────────────────────────────────────────────────────


@router.post("/packages", response_model=PackageRead, status_code=status.HTTP_201_CREATED)
async def create_package(
    body: PackageCreate, session: SessionDep, _user: CurrentUser
) -> Package:
    pkg = Package(**body.model_dump())
    session.add(pkg)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "package name already exists") from exc
    return pkg


@router.get("/packages", response_model=list[PackageRead])
async def list_packages(
    session: SessionDep,
    _user: CurrentUser,
    location_id: int | None = None,
) -> list[Package]:
    stmt = select(Package).where(Package.deleted_at.is_(None))
    if location_id is not None:
        stmt = stmt.where(Package.location_id == location_id)
    return list((await session.execute(stmt.order_by(Package.name))).scalars().all())


@router.get("/packages/{package_id}", response_model=PackageRead)
async def get_package(package_id: int, session: SessionDep, _user: CurrentUser) -> Package:
    pkg = await session.get(Package, package_id)
    if pkg is None or pkg.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "package not found")
    return pkg


# ── Putaway Rules ──────────────────────────────────────────────────────


@router.post("/putaway-rules", response_model=PutawayRuleRead, status_code=status.HTTP_201_CREATED)
async def create_putaway_rule(
    body: PutawayRuleCreate, session: SessionDep, _user: CurrentUser
) -> PutawayRule:
    rule = PutawayRule(**body.model_dump())
    session.add(rule)
    await session.flush()
    return rule


@router.get("/putaway-rules", response_model=list[PutawayRuleRead])
async def list_putaway_rules(
    session: SessionDep,
    _user: CurrentUser,
    location_id: int | None = None,
    active_only: bool = True,
) -> list[PutawayRule]:
    stmt = select(PutawayRule).where(PutawayRule.deleted_at.is_(None))
    if location_id is not None:
        stmt = stmt.where(PutawayRule.location_id == location_id)
    if active_only:
        stmt = stmt.where(PutawayRule.active.is_(True))
    return list(
        (await session.execute(stmt.order_by(PutawayRule.sequence))).scalars().all()
    )


@router.delete("/putaway-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_putaway_rule(
    rule_id: int, session: SessionDep, _user: CurrentUser
) -> None:
    rule = await session.get(PutawayRule, rule_id)
    if rule is None or rule.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "putaway rule not found")
    await session.delete(rule)
    await session.flush()


# ── Reorder Rules ──────────────────────────────────────────────────────


@router.post("/reorder-rules", response_model=ReorderRuleRead, status_code=status.HTTP_201_CREATED)
async def create_reorder_rule(
    body: ReorderRuleCreate, session: SessionDep, _user: CurrentUser
) -> ReorderRule:
    rule = ReorderRule(**body.model_dump())
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "reorder rule already exists for this product/location combination",
        ) from exc
    return rule


@router.get("/reorder-rules", response_model=list[ReorderRuleRead])
async def list_reorder_rules(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    active_only: bool = True,
) -> list[ReorderRule]:
    stmt = select(ReorderRule).where(ReorderRule.deleted_at.is_(None))
    if warehouse_id is not None:
        stmt = stmt.where(ReorderRule.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(ReorderRule.product_id == product_id)
    if active_only:
        stmt = stmt.where(ReorderRule.active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


@router.put("/reorder-rules/{rule_id}", response_model=ReorderRuleRead)
async def update_reorder_rule(
    rule_id: int, body: ReorderRuleUpdate, session: SessionDep, _user: CurrentUser
) -> ReorderRule:
    rule = await session.get(ReorderRule, rule_id)
    if rule is None or rule.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reorder rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await session.flush()
    return rule


@router.delete("/reorder-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reorder_rule(
    rule_id: int, session: SessionDep, _user: CurrentUser
) -> None:
    rule = await session.get(ReorderRule, rule_id)
    if rule is None or rule.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reorder rule not found")
    await session.delete(rule)
    await session.flush()


# ── Stock Valuation Layers (read-only) ─────────────────────────────────


@router.get("/valuation-layers", response_model=list[StockValuationLayerRead])
async def list_valuation_layers(
    session: SessionDep,
    _user: CurrentUser,
    product_id: int | None = None,
    transfer_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StockValuationLayer]:
    stmt = (
        select(StockValuationLayer)
        .where(StockValuationLayer.deleted_at.is_(None))
        .order_by(StockValuationLayer.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if product_id is not None:
        stmt = stmt.where(StockValuationLayer.product_id == product_id)
    if transfer_id is not None:
        stmt = stmt.where(StockValuationLayer.transfer_id == transfer_id)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/valuation-layers/{layer_id}", response_model=StockValuationLayerRead)
async def get_valuation_layer(
    layer_id: int, session: SessionDep, _user: CurrentUser
) -> StockValuationLayer:
    layer = await session.get(StockValuationLayer, layer_id)
    if layer is None or layer.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "valuation layer not found")
    return layer


# ── Scrap Orders ───────────────────────────────────────────────────────


@router.post("/scrap-orders", response_model=ScrapOrderRead, status_code=status.HTTP_201_CREATED)
async def create_scrap_order(
    body: ScrapOrderCreate, session: SessionDep, _user: CurrentUser
) -> ScrapOrder:
    count = len(
        list(
            (
                await session.execute(select(ScrapOrder).where(ScrapOrder.deleted_at.is_(None)))
            ).scalars().all()
        )
    )
    name = f"SCRAP/{count + 1:06d}"
    scrap = ScrapOrder(name=name, state="draft", **body.model_dump())
    session.add(scrap)
    await session.flush()
    return scrap


@router.get("/scrap-orders", response_model=list[ScrapOrderRead])
async def list_scrap_orders(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    product_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ScrapOrder]:
    stmt = (
        select(ScrapOrder)
        .where(ScrapOrder.deleted_at.is_(None))
        .order_by(ScrapOrder.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(ScrapOrder.state == state)
    if product_id is not None:
        stmt = stmt.where(ScrapOrder.product_id == product_id)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/scrap-orders/{scrap_id}", response_model=ScrapOrderRead)
async def get_scrap_order(scrap_id: int, session: SessionDep, _user: CurrentUser) -> ScrapOrder:
    scrap = await session.get(ScrapOrder, scrap_id)
    if scrap is None or scrap.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scrap order not found")
    return scrap


@router.post("/scrap-orders/{scrap_id}/validate", response_model=ScrapOrderRead)
async def validate_scrap_order(
    scrap_id: int, session: SessionDep, _user: CurrentUser
) -> ScrapOrder:
    scrap = await get_scrap_order(scrap_id, session, _user)
    return await validate_scrap(session, scrap)


@router.post("/scrap-orders/{scrap_id}/cancel", response_model=ScrapOrderRead)
async def cancel_scrap_order(
    scrap_id: int, session: SessionDep, _user: CurrentUser
) -> ScrapOrder:
    from backend.core.workflow import WorkflowError

    scrap = await get_scrap_order(scrap_id, session, _user)
    try:
        scrap.transition("cancelled")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return scrap


# ── Landed Costs ───────────────────────────────────────────────────────


@router.post("/landed-costs", response_model=LandedCostRead, status_code=status.HTTP_201_CREATED)
async def create_landed_cost(
    body: LandedCostCreate, session: SessionDep, _user: CurrentUser
) -> LandedCost:
    count = len(
        list(
            (
                await session.execute(select(LandedCost).where(LandedCost.deleted_at.is_(None)))
            ).scalars().all()
        )
    )
    name = body.name or f"LC/{count + 1:06d}"
    payload = body.model_dump(exclude={"lines", "transfer_ids", "name"})
    lc = LandedCost(name=name, state="draft", **payload)
    session.add(lc)
    await session.flush()

    for line_data in body.lines:
        lc_line = LandedCostLine(landed_cost_id=lc.id, **line_data.model_dump())
        session.add(lc_line)

    for t_id in body.transfer_ids:
        link = LandedCostTransfer(landed_cost_id=lc.id, transfer_id=t_id)
        session.add(link)

    await session.flush()
    await session.refresh(lc, attribute_names=["lines", "transfer_links"])
    return lc


@router.get("/landed-costs", response_model=list[LandedCostRead])
async def list_landed_costs(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[LandedCost]:
    stmt = (
        select(LandedCost)
        .where(LandedCost.deleted_at.is_(None))
        .options(selectinload(LandedCost.lines))
        .order_by(LandedCost.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(LandedCost.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/landed-costs/{lc_id}", response_model=LandedCostRead)
async def get_landed_cost(lc_id: int, session: SessionDep, _user: CurrentUser) -> LandedCost:
    stmt = (
        select(LandedCost)
        .where(LandedCost.id == lc_id)
        .options(selectinload(LandedCost.lines), selectinload(LandedCost.transfer_links))
    )
    lc = (await session.execute(stmt)).scalar_one_or_none()
    if lc is None or lc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "landed cost not found")
    return lc


@router.post("/landed-costs/{lc_id}/post", response_model=LandedCostRead)
async def post_landed_cost_route(
    lc_id: int, session: SessionDep, _user: CurrentUser
) -> LandedCost:
    stmt = (
        select(LandedCost)
        .where(LandedCost.id == lc_id)
        .options(selectinload(LandedCost.lines), selectinload(LandedCost.transfer_links))
    )
    lc = (await session.execute(stmt)).scalar_one_or_none()
    if lc is None or lc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "landed cost not found")
    return await post_landed_cost(session, lc)


@router.post("/landed-costs/{lc_id}/cancel", response_model=LandedCostRead)
async def cancel_landed_cost(lc_id: int, session: SessionDep, _user: CurrentUser) -> LandedCost:
    from backend.core.workflow import WorkflowError

    lc = await get_landed_cost(lc_id, session, _user)
    try:
        lc.transition("cancelled")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return lc


# ── Return / Backorder on existing transfer ────────────────────────────


@router.post("/transfers/{transfer_id}/return", response_model=TransferRead)
async def return_transfer(
    transfer_id: int, body: ReturnCreate, session: SessionDep, _user: CurrentUser
) -> Transfer:
    stmt = (
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .options(selectinload(Transfer.lines))
    )
    original = (await session.execute(stmt)).scalar_one_or_none()
    if original is None or original.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")

    return await create_return_transfer(
        session,
        original,
        [item.model_dump() for item in body.lines],
    )


@router.post("/transfers/{transfer_id}/backorder", response_model=TransferRead)
async def backorder_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> Transfer:
    stmt = (
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .options(selectinload(Transfer.lines))
    )
    original = (await session.execute(stmt)).scalar_one_or_none()
    if original is None or original.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")

    backorder = await create_backorder(session, original)
    if backorder is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no remaining quantities — backorder not needed")
    return backorder
