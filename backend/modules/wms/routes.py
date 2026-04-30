"""HTTP routes for the WMS module."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.wms.models import (
    LOCATION_USAGES,
    PRODUCT_TYPES,
    Location,
    Lot,
    Product,
    ProductCategory,
    Uom,
    UomCategory,
    Warehouse,
    Zone,
)
from backend.modules.wms.schemas import (
    LocationCreate,
    LocationRead,
    LotCreate,
    LotRead,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCreate,
    ProductRead,
    UomCategoryCreate,
    UomCategoryRead,
    UomCreate,
    UomRead,
    WarehouseCreate,
    WarehouseRead,
    ZoneCreate,
    ZoneRead,
)

router = APIRouter(prefix="/wms", tags=["wms"])


# ── Warehouses ─────────────────────────────────────────────────────────


@router.post("/warehouses", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate, session: SessionDep, _user: CurrentUser
) -> Warehouse:
    wh = Warehouse(code=body.code, name=body.name, address=body.address, active=True)
    session.add(wh)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "warehouse code already exists") from exc
    return wh


@router.get("/warehouses", response_model=list[WarehouseRead])
async def list_warehouses(session: SessionDep, _user: CurrentUser) -> list[Warehouse]:
    stmt = select(Warehouse).where(Warehouse.deleted_at.is_(None)).order_by(Warehouse.code)
    return list((await session.execute(stmt)).scalars().all())


# ── Zones ──────────────────────────────────────────────────────────────


@router.post("/zones", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
async def create_zone(body: ZoneCreate, session: SessionDep, _user: CurrentUser) -> Zone:
    wh = await session.get(Warehouse, body.warehouse_id)
    if wh is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "warehouse not found")
    zone = Zone(
        warehouse_id=body.warehouse_id,
        code=body.code,
        name=body.name,
        color_hex=body.color_hex,
        note=body.note,
        active=True,
    )
    session.add(zone)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "zone code already exists for warehouse") from exc
    return zone


@router.get("/zones", response_model=list[ZoneRead])
async def list_zones(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
) -> list[Zone]:
    stmt = select(Zone).where(Zone.deleted_at.is_(None))
    if warehouse_id is not None:
        stmt = stmt.where(Zone.warehouse_id == warehouse_id)
    return list((await session.execute(stmt.order_by(Zone.code))).scalars().all())


# ── UoMs ───────────────────────────────────────────────────────────────


@router.post(
    "/uom-categories", response_model=UomCategoryRead, status_code=status.HTTP_201_CREATED
)
async def create_uom_category(
    body: UomCategoryCreate, session: SessionDep, _user: CurrentUser
) -> UomCategory:
    cat = UomCategory(name=body.name)
    session.add(cat)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "category name already exists") from exc
    return cat


@router.get("/uom-categories", response_model=list[UomCategoryRead])
async def list_uom_categories(session: SessionDep, _user: CurrentUser) -> list[UomCategory]:
    return list(
        (await session.execute(select(UomCategory).order_by(UomCategory.name))).scalars().all()
    )


@router.post("/uoms", response_model=UomRead, status_code=status.HTTP_201_CREATED)
async def create_uom(body: UomCreate, session: SessionDep, _user: CurrentUser) -> Uom:
    cat = await session.get(UomCategory, body.category_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "uom category not found")
    uom = Uom(
        category_id=body.category_id,
        name=body.name,
        uom_type=body.uom_type,
        factor=body.factor,
        rounding=body.rounding,
        active=True,
    )
    session.add(uom)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "uom name already exists in category") from exc
    return uom


@router.get("/uoms", response_model=list[UomRead])
async def list_uoms(session: SessionDep, _user: CurrentUser) -> list[Uom]:
    return list(
        (await session.execute(select(Uom).order_by(Uom.name))).scalars().all()
    )


# ── Locations ──────────────────────────────────────────────────────────


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate, session: SessionDep, _user: CurrentUser
) -> Location:
    if body.usage not in LOCATION_USAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid usage: {body.usage}")
    if body.warehouse_id is not None:
        if (await session.get(Warehouse, body.warehouse_id)) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "warehouse not found")
    if body.parent_id is not None:
        if (await session.get(Location, body.parent_id)) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "parent location not found")

    loc = Location(
        warehouse_id=body.warehouse_id,
        parent_id=body.parent_id,
        zone_id=body.zone_id,
        name=body.name,
        usage=body.usage,
        barcode=body.barcode,
        active=True,
    )
    session.add(loc)
    await session.flush()
    return loc


@router.get("/locations", response_model=list[LocationRead])
async def list_locations(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
    usage: str | None = None,
) -> list[Location]:
    stmt = select(Location).where(Location.deleted_at.is_(None))
    if warehouse_id is not None:
        stmt = stmt.where(Location.warehouse_id == warehouse_id)
    if usage is not None:
        if usage not in LOCATION_USAGES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid usage: {usage}")
        stmt = stmt.where(Location.usage == usage)
    return list((await session.execute(stmt.order_by(Location.name))).scalars().all())


# ── Product categories ─────────────────────────────────────────────────


@router.post(
    "/product-categories", response_model=ProductCategoryRead, status_code=status.HTTP_201_CREATED
)
async def create_product_category(
    body: ProductCategoryCreate, session: SessionDep, _user: CurrentUser
) -> ProductCategory:
    if body.parent_id is not None:
        if (await session.get(ProductCategory, body.parent_id)) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "parent category not found")
    cat = ProductCategory(parent_id=body.parent_id, name=body.name)
    session.add(cat)
    await session.flush()
    return cat


@router.get("/product-categories", response_model=list[ProductCategoryRead])
async def list_product_categories(
    session: SessionDep, _user: CurrentUser
) -> list[ProductCategory]:
    return list(
        (
            await session.execute(
                select(ProductCategory)
                .where(ProductCategory.deleted_at.is_(None))
                .order_by(ProductCategory.name)
            )
        )
        .scalars()
        .all()
    )


# ── Products ───────────────────────────────────────────────────────────


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, session: SessionDep, _user: CurrentUser) -> Product:
    if body.type not in PRODUCT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid type: {body.type}")
    if (await session.get(Uom, body.uom_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "uom not found")
    if body.category_id is not None:
        if (await session.get(ProductCategory, body.category_id)) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "product category not found")

    product = Product(
        default_code=body.default_code,
        barcode=body.barcode,
        name=body.name,
        description=body.description,
        type=body.type,
        category_id=body.category_id,
        uom_id=body.uom_id,
        list_price=body.list_price,
        standard_price=body.standard_price,
        active=True,
    )
    session.add(product)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "default_code or barcode already exists") from exc
    return product


@router.get("/products", response_model=list[ProductRead])
async def list_products(
    session: SessionDep,
    _user: CurrentUser,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Product]:
    stmt = select(Product).where(Product.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Product.name.ilike(like)) | (Product.default_code.ilike(like)))
    return list(
        (
            await session.execute(stmt.order_by(Product.default_code).limit(limit).offset(offset))
        )
        .scalars()
        .all()
    )


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, session: SessionDep, _user: CurrentUser) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
    return product


# ── Lots ───────────────────────────────────────────────────────────────


@router.post("/lots", response_model=LotRead, status_code=status.HTTP_201_CREATED)
async def create_lot(body: LotCreate, session: SessionDep, _user: CurrentUser) -> Lot:
    if (await session.get(Product, body.product_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
    lot = Lot(
        product_id=body.product_id,
        name=body.name,
        expiration_date=body.expiration_date,
        note=body.note,
    )
    session.add(lot)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "lot name already exists for product") from exc
    return lot


@router.get("/lots", response_model=list[LotRead])
async def list_lots(
    session: SessionDep,
    _user: CurrentUser,
    product_id: int | None = None,
) -> list[Lot]:
    stmt = select(Lot).where(Lot.deleted_at.is_(None))
    if product_id is not None:
        stmt = stmt.where(Lot.product_id == product_id)
    return list((await session.execute(stmt.order_by(Lot.name))).scalars().all())
