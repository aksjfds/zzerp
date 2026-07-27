from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class WorkOrderMaterial(Base):
    __tablename__ = "work_order_material"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_material_quantity"),
        ForeignKeyConstraint(
            ["repository_id", "production_item_id"],
            ["repository.id", "repository.production_item_id"],
            name="fk_work_order_material_repository_item",
        ),
        Index(
            "idx_work_order_material_production_item",
            "production_item_id",
        ),
        Index("idx_work_order_material_repository", "repository_id"),
        UniqueConstraint(
            "work_order_id",
            "production_item_id",
            name="uq_work_order_material_item",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_item.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
