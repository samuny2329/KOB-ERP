"""KOB-WMS extension models — racks, pickfaces, couriers.

Stay in the ``wms`` schema since they're warehouse-master-data tables.
The pick/pack/ship transactional flow lives separately in the
``outbound`` module.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.modules.wms.models import Location, Product, Zone


class Rack(BaseModel):
    """Bulk storage rack tied to a zone — usually mapped to one location."""

    __tablename__ = "rack"
    __table_args__ = (
        UniqueConstraint("zone_id", "code", name="uq_rack_zone_code"),
        {"schema": "wms"},
    )

    zone_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.zone.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    zone: Mapped[Zone] = relationship()
    location: Mapped[Location | None] = relationship()


class Pickface(BaseModel):
    """Fast-pick bin — replenished from a Rack when stock runs low."""

    __tablename__ = "pickface"
    __table_args__ = (
        UniqueConstraint("zone_id", "code", name="uq_pickface_zone_code"),
        {"schema": "wms"},
    )

    zone_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.zone.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    min_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    zone: Mapped[Zone] = relationship()
    location: Mapped[Location] = relationship()
    product: Mapped[Product] = relationship()


class Courier(BaseModel):
    """Carrier master — Thai Post, Flash, J&T, Shopee Express, etc."""

    __tablename__ = "courier"
    __table_args__ = ({"schema": "wms"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    tracking_url_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
