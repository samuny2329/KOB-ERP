"""HTTP routes for the ops module — boxes, platforms, KPI, reports."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.ops.models import (
    BoxSize,
    BoxUsage,
    DailyReport,
    KpiAlert,
    KpiTarget,
    MonthlyReport,
    PlatformConfig,
    PlatformOrder,
    WorkerKpi,
)
from backend.modules.ops.schemas import (
    BoxSizeCreate,
    BoxSizeRead,
    BoxUsageCreate,
    BoxUsageRead,
    DailyReportRead,
    KpiAlertRead,
    KpiTargetCreate,
    KpiTargetRead,
    MonthlyReportRead,
    PlatformConfigCreate,
    PlatformConfigRead,
    PlatformOrderCreate,
    PlatformOrderRead,
    WorkerKpiCreate,
    WorkerKpiRead,
)

router = APIRouter(prefix="/ops", tags=["ops"])


# ── Box sizes ─────────────────────────────────────────────────────────


@router.get("/box-sizes", response_model=list[BoxSizeRead])
async def list_box_sizes(session: SessionDep, _user: CurrentUser) -> list[BoxSize]:
    rows = (
        await session.execute(
            select(BoxSize).where(BoxSize.deleted_at.is_(None)).order_by(BoxSize.code)
        )
    ).scalars().all()
    return list(rows)


@router.post("/box-sizes", response_model=BoxSizeRead, status_code=status.HTTP_201_CREATED)
async def create_box_size(body: BoxSizeCreate, session: SessionDep, _user: CurrentUser) -> BoxSize:
    box = BoxSize(**body.model_dump())
    session.add(box)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "box code already exists") from exc
    return box


@router.post("/box-usage", response_model=BoxUsageRead, status_code=status.HTTP_201_CREATED)
async def log_box_usage(body: BoxUsageCreate, session: SessionDep, _user: CurrentUser) -> BoxUsage:
    usage = BoxUsage(**body.model_dump())
    session.add(usage)
    await session.flush()
    return usage


@router.get("/box-usage", response_model=list[BoxUsageRead])
async def list_box_usage(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[BoxUsage]:
    stmt = select(BoxUsage).where(BoxUsage.deleted_at.is_(None))
    if warehouse_id:
        stmt = stmt.where(BoxUsage.warehouse_id == warehouse_id)
    if from_date:
        stmt = stmt.where(BoxUsage.usage_date >= from_date)
    if to_date:
        stmt = stmt.where(BoxUsage.usage_date <= to_date)
    return list((await session.execute(stmt.order_by(BoxUsage.usage_date.desc()))).scalars().all())


# ── Platform configs ──────────────────────────────────────────────────


@router.get("/platform-configs", response_model=list[PlatformConfigRead])
async def list_platform_configs(session: SessionDep, _user: CurrentUser) -> list[PlatformConfig]:
    rows = (
        await session.execute(
            select(PlatformConfig).where(PlatformConfig.deleted_at.is_(None))
        )
    ).scalars().all()
    return list(rows)


@router.post(
    "/platform-configs", response_model=PlatformConfigRead, status_code=status.HTTP_201_CREATED
)
async def create_platform_config(
    body: PlatformConfigCreate, session: SessionDep, _user: CurrentUser
) -> PlatformConfig:
    cfg = PlatformConfig(**body.model_dump())
    session.add(cfg)
    await session.flush()
    return cfg


# ── Platform orders ───────────────────────────────────────────────────


@router.get("/platform-orders", response_model=list[PlatformOrderRead])
async def list_platform_orders(
    session: SessionDep,
    _user: CurrentUser,
    platform: str | None = None,
    status_filter: str | None = None,
) -> list[PlatformOrder]:
    stmt = (
        select(PlatformOrder)
        .where(PlatformOrder.deleted_at.is_(None))
        .options(selectinload(PlatformOrder.lines))
        .order_by(PlatformOrder.created_at.desc())
    )
    if platform:
        stmt = stmt.where(PlatformOrder.platform == platform)
    if status_filter:
        stmt = stmt.where(PlatformOrder.status == status_filter)
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/platform-orders", response_model=PlatformOrderRead, status_code=status.HTTP_201_CREATED
)
async def ingest_platform_order(
    body: PlatformOrderCreate, session: SessionDep, _user: CurrentUser
) -> PlatformOrder:
    order = PlatformOrder(**body.model_dump())
    session.add(order)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "external_order_id already exists"
        ) from exc
    return order


@router.patch("/platform-orders/{order_id}/status", response_model=PlatformOrderRead)
async def update_platform_order_status(
    order_id: int,
    new_status: str,
    session: SessionDep,
    _user: CurrentUser,
) -> PlatformOrder:
    order = await session.get(PlatformOrder, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    order.status = new_status
    await session.flush()
    await session.refresh(order, ["lines"])
    return order


# ── Worker KPI ────────────────────────────────────────────────────────


@router.get("/kpi/workers", response_model=list[WorkerKpiRead])
async def list_worker_kpis(
    session: SessionDep,
    _user: CurrentUser,
    user_id: int | None = None,
    from_date: date | None = None,
) -> list[WorkerKpi]:
    stmt = select(WorkerKpi).where(WorkerKpi.deleted_at.is_(None))
    if user_id:
        stmt = stmt.where(WorkerKpi.user_id == user_id)
    if from_date:
        stmt = stmt.where(WorkerKpi.kpi_date >= from_date)
    return list(
        (await session.execute(stmt.order_by(WorkerKpi.kpi_date.desc()))).scalars().all()
    )


@router.post("/kpi/workers", response_model=WorkerKpiRead, status_code=status.HTTP_201_CREATED)
async def upsert_worker_kpi(
    body: WorkerKpiCreate, session: SessionDep, _user: CurrentUser
) -> WorkerKpi:
    kpi = WorkerKpi(**body.model_dump())
    session.add(kpi)
    await session.flush()
    return kpi


@router.get("/kpi/targets", response_model=list[KpiTargetRead])
async def list_kpi_targets(session: SessionDep, _user: CurrentUser) -> list[KpiTarget]:
    rows = (
        await session.execute(select(KpiTarget).where(KpiTarget.deleted_at.is_(None)))
    ).scalars().all()
    return list(rows)


@router.post("/kpi/targets", response_model=KpiTargetRead, status_code=status.HTTP_201_CREATED)
async def create_kpi_target(
    body: KpiTargetCreate, session: SessionDep, _user: CurrentUser
) -> KpiTarget:
    target = KpiTarget(**body.model_dump())
    session.add(target)
    await session.flush()
    return target


@router.get("/kpi/alerts", response_model=list[KpiAlertRead])
async def list_kpi_alerts(
    session: SessionDep,
    _user: CurrentUser,
    unresolved_only: bool = True,
) -> list[KpiAlert]:
    stmt = select(KpiAlert).where(KpiAlert.deleted_at.is_(None))
    if unresolved_only:
        stmt = stmt.where(KpiAlert.resolved.is_(False))
    return list(
        (await session.execute(stmt.order_by(KpiAlert.created_at.desc()))).scalars().all()
    )


@router.post("/kpi/alerts/{alert_id}/resolve", response_model=KpiAlertRead)
async def resolve_kpi_alert(
    alert_id: int, session: SessionDep, _user: CurrentUser
) -> KpiAlert:
    alert = await session.get(KpiAlert, alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return alert


# ── Reports ───────────────────────────────────────────────────────────


@router.get("/reports/daily", response_model=list[DailyReportRead])
async def list_daily_reports(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[DailyReport]:
    stmt = select(DailyReport).where(DailyReport.deleted_at.is_(None))
    if warehouse_id:
        stmt = stmt.where(DailyReport.warehouse_id == warehouse_id)
    if from_date:
        stmt = stmt.where(DailyReport.report_date >= from_date)
    if to_date:
        stmt = stmt.where(DailyReport.report_date <= to_date)
    return list(
        (await session.execute(stmt.order_by(DailyReport.report_date.desc()))).scalars().all()
    )


@router.get("/reports/monthly", response_model=list[MonthlyReportRead])
async def list_monthly_reports(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
    year: int | None = None,
) -> list[MonthlyReport]:
    stmt = select(MonthlyReport).where(MonthlyReport.deleted_at.is_(None))
    if warehouse_id:
        stmt = stmt.where(MonthlyReport.warehouse_id == warehouse_id)
    if year:
        stmt = stmt.where(MonthlyReport.year == year)
    return list(
        (
            await session.execute(
                stmt.order_by(MonthlyReport.year.desc(), MonthlyReport.month.desc())
            )
        ).scalars().all()
    )
