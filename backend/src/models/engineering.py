from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("factory_code", name="uq_product_factory_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    factory_code: Mapped[str] = mapped_column(Text, nullable=False)
    customer_code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
    )
    bom_items: Mapped[list[ProductBom]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductBom.sort_order",
    )
    process_flows: Mapped[list[ProductProcessFlow]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductProcessFlow.product_version",
    )


class ProductBom(Base):
    __tablename__ = "product_bom"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "product_version", "part_no", name="uq_product_bom_part_no"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    part_name: Mapped[str] = mapped_column(Text, nullable=False)
    part_no: Mapped[str] = mapped_column(Text, nullable=False)
    pcs: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
    )
    product: Mapped[Product] = relationship(back_populates="bom_items")


class ProductProcessFlow(Base):
    __tablename__ = "product_process_flow"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "product_version", name="uq_product_process_flow_version"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    flow_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=lambda: {"schema_version": 1, "nodes": [], "edges": []},
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
    )
    product: Mapped[Product] = relationship(back_populates="process_flows")
