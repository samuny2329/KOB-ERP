"""WMS domain models — warehouses, locations, zones, products, lots, UoMs.

Re-implementation of Odoo's `stock` / `product` / `uom` model concepts in
SQLAlchemy 2.0.  No source code is copied from Odoo; we only mirror the
shape of the data and adapt to idiomatic Python/SQLAlchemy.
"""

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel


# ── UoM ────────────────────────────────────────────────────────────────


class UomCategory(BaseModel):
    """UoM groupings — e.g. Length, Weight, Volume, Time, Unit.

    Conversions are only valid within a single category.
    """

    __tablename__ = "uom_category"
    __table_args__ = ({"schema": "wms"},)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    uoms: Mapped[list["Uom"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )


class Uom(BaseModel):
    """Unit of measure within a category.

    ``uom_type`` ∈ {reference, bigger, smaller}.  Each category has
    exactly one reference uom; ``factor`` expresses other uoms relative
    to it (factor > 1 for "bigger", < 1 for "smaller").
    """

    __tablename__ = "uom"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_uom_cat_name"),
        {"schema": "wms"},
    )

    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.uom_category.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    uom_type: Mapped[str] = mapped_column(String(10), nullable=False, default="reference")
    factor: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False, default=1.0)
    rounding: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False, default=0.01)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[UomCategory] = relationship(back_populates="uoms")


# ── Warehouse / Zone / Location ────────────────────────────────────────


class Warehouse(BaseModel):
    """Physical warehouse — root of the location hierarchy."""

    __tablename__ = "warehouse"
    __table_args__ = ({"schema": "wms"},)

    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    locations: Mapped[list["Location"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )
    zones: Mapped[list["Zone"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )


class Zone(BaseModel):
    """Functional grouping of locations inside a warehouse (KOB-WMS extension).

    Zones are NOT the location hierarchy — a single zone can span many
    physical locations.  Color is for UI.
    """

    __tablename__ = "zone"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_zone_warehouse_code"),
        {"schema": "wms"},
    )

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    warehouse: Mapped[Warehouse] = relationship(back_populates="zones")


# Allowed values for Location.usage — kept as a tuple so seed scripts &
# schema validation stay in sync.
LOCATION_USAGES = ("supplier", "customer", "internal", "inventory", "transit", "view", "production", "scrap")

# Removal strategies — order in which lots are picked from a location.
REMOVAL_STRATEGIES = ("fifo", "fefo", "lifo", "closest")


class Location(BaseModel):
    """Physical / logical place that can hold inventory.

    ``parent_id`` builds a tree (e.g. WH → Stock → Shelf-A).  ``usage``
    distinguishes physical (internal) from virtual (supplier / customer /
    inventory adjustment / transit / scrap) locations.
    ``removal_strategy`` controls pick order for outbound moves.
    ``putaway_strategy`` hints to putaway rules how to select a child location.
    """

    __tablename__ = "location"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "barcode", name="uq_location_barcode"),
        {"schema": "wms"},
    )

    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.zone.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    complete_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usage: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    barcode: Mapped[str | None] = mapped_column(String(60), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Odoo 19 additions
    removal_strategy: Mapped[str] = mapped_column(String(10), nullable=False, default="fifo")
    max_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_scrap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=10)

    warehouse: Mapped[Warehouse | None] = relationship(back_populates="locations")
    parent: Mapped["Location | None"] = relationship(
        remote_side="Location.id",
        backref="children",
    )
    zone: Mapped[Zone | None] = relationship()


# ── Product ────────────────────────────────────────────────────────────


class ProductCategory(BaseModel):
    __tablename__ = "product_category"
    __table_args__ = ({"schema": "wms"},)

    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    complete_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    parent: Mapped["ProductCategory | None"] = relationship(
        remote_side="ProductCategory.id",
        backref="children",
    )


PRODUCT_TYPES = ("consu", "service", "product")  # mirrors Odoo
TRACKING_TYPES = ("none", "lot", "serial")  # none=no tracking, lot=batch, serial=unit
COST_METHODS = ("standard", "fifo", "avco")  # standard=fixed cost, fifo, average cost


class Product(BaseModel):
    """Sellable / stockable item.

    Odoo 19 additions: tracking (lot/serial/none), cost_method (fifo/avco/standard),
    weight/volume for logistics, purchase/sales uom, reorder point fields.
    """

    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("default_code", name="uq_product_default_code"),
        {"schema": "wms"},
    )

    default_code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="product")
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="SET NULL"), nullable=True
    )
    uom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.uom.id", ondelete="RESTRICT"), nullable=False
    )
    uom_purchase_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.uom.id", ondelete="SET NULL"), nullable=True
    )
    list_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    standard_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Odoo 19 additions
    tracking: Mapped[str] = mapped_column(String(10), nullable=False, default="none")
    cost_method: Mapped[str] = mapped_column(String(10), nullable=False, default="standard")
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    volume_m3: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    purchase_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sale_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Computed/cached average cost (updated by valuation service)
    avg_cost: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False, default=0)

    category: Mapped[ProductCategory | None] = relationship()
    uom: Mapped[Uom] = relationship(foreign_keys=[uom_id])
    uom_purchase: Mapped[Uom | None] = relationship(foreign_keys=[uom_purchase_id])


class Lot(BaseModel):
    """Lot or serial number bound to a single product.

    Odoo 19: lot_type distinguishes batch lot from unique serial number.
    Added use_date (best-before) and removal_date for FEFO strategies.
    """

    __tablename__ = "lot"
    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uq_lot_product_name"),
        {"schema": "wms"},
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    lot_type: Mapped[str] = mapped_column(String(10), nullable=False, default="lot")
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    use_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    removal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # supplier ref for traceability
    supplier_lot_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)

    product: Mapped[Product] = relationship()
