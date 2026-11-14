from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zzerp.database import Base


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("factory_code", name="uq_product_factory_code"),
        UniqueConstraint("id", "customer_id", name="uq_product_customer_context"),
        CheckConstraint("revision > 0", name="ck_product_revision"),
        Index("idx_product_customer", "customer_id", text("updated_at DESC"), text("id DESC")),
        Index(
            "idx_product_product_name_trgm",
            "product_name",
            postgresql_using="gin",
            postgresql_ops={"product_name": "gin_trgm_ops"},
        ),
        Index(
            "idx_product_factory_code_trgm",
            "factory_code",
            postgresql_using="gin",
            postgresql_ops={"factory_code": "gin_trgm_ops"},
        ),
        Index(
            "idx_product_customer_code_trgm",
            "customer_code",
            postgresql_using="gin",
            postgresql_ops={"customer_code": "gin_trgm_ops"},
        ),
        Index("idx_product_updated", text("updated_at DESC"), text("id DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", name="fk_product_customer"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    factory_code: Mapped[str] = mapped_column(Text, nullable=False)
    customer_code: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    bom_items: Mapped[list[ProductBom]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductBom.sort_order",
    )
    process_flows: Mapped[list[ProductProcessFlow]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductProcessFlow.appearance_id",
    )
    appearances: Mapped[list[ProductAppearance]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="ProductAppearance.product_id",
        primaryjoin="Product.id == ProductAppearance.product_id",
        order_by="ProductAppearance.id",
    )


class ProductAppearance(Base):
    __tablename__ = "product_appearance"
    __table_args__ = (
        UniqueConstraint("product_id", "appearance_name", name="uq_product_appearance_name"),
        UniqueConstraint("product_id", "id", name="uq_product_appearance_product"),
        CheckConstraint("appearance_name ~ '[^[:space:]]'", name="ck_product_appearance_name"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", name="fk_product_appearance_product", ondelete="CASCADE"),
        nullable=False,
    )
    appearance_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    product: Mapped[Product] = relationship(back_populates="appearances")


class ProductBom(Base):
    __tablename__ = "product_bom"
    __table_args__ = (
        UniqueConstraint("id", "product_id", name="uq_product_bom_product"),
        UniqueConstraint("product_id", "part_no", name="uq_product_bom_part_no"),
        UniqueConstraint(
            "product_id",
            "sort_order",
            name="uq_product_bom_sort_order",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("pcs > 0", name="ck_product_bom_pcs"),
        CheckConstraint("sort_order > 0", name="ck_product_bom_sort_order"),
        Index("idx_product_bom_product", "product_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", name="fk_product_bom_product", ondelete="CASCADE"),
        nullable=False,
    )
    part_name: Mapped[str] = mapped_column(Text, nullable=False)
    part_no: Mapped[str] = mapped_column(Text, nullable=False)
    pcs: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    product: Mapped[Product] = relationship(back_populates="bom_items")


class ProductProcessFlow(Base):
    __tablename__ = "product_process_flow"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "appearance_id"],
            ["product_appearance.product_id", "product_appearance.id"],
            name="fk_product_process_flow_appearance",
            ondelete="CASCADE",
        ),
        UniqueConstraint("product_id", "appearance_id", name="uq_product_process_flow_appearance"),
        CheckConstraint(
            "(jsonb_typeof(flow_json) = 'object' AND jsonb_typeof(flow_json->'schema_version') = 'number' AND flow_json->>'schema_version' = '8' AND jsonb_typeof(flow_json->'nodes') = 'array' AND jsonb_typeof(flow_json->'edges') = 'array') IS TRUE",
            name="ck_process_flow_structure",
        ),
        CheckConstraint(
            "draft_flow_json IS NULL OR (jsonb_typeof(draft_flow_json) = 'object' AND jsonb_typeof(draft_flow_json->'schema_version') = 'number' AND draft_flow_json->>'schema_version' = '8' AND jsonb_typeof(draft_flow_json->'nodes') = 'array' AND jsonb_typeof(draft_flow_json->'edges') = 'array') IS TRUE",
            name="ck_process_flow_draft_structure",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", name="fk_product_process_flow_product", ondelete="CASCADE"),
        nullable=False,
    )
    appearance_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    flow_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
        default=lambda: {"schema_version": 8, "nodes": [], "edges": []},
        server_default=text('\'{"schema_version": 8, "nodes": [], "edges": []}\''),
    )
    draft_flow_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    product: Mapped[Product] = relationship(back_populates="process_flows")


class ProductDepartmentRoute(Base):
    __tablename__ = "product_department_route"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "appearance_id"],
            ["product_appearance.product_id", "product_appearance.id"],
            name="fk_product_department_route_appearance",
            ondelete="CASCADE",
        ),
        Index("idx_product_department_route_department", "department_code", "product_id"),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", name="fk_product_department_route_product", ondelete="CASCADE"),
        primary_key=True,
    )
    appearance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    material_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    department_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    department_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("production_department.code", name="fk_product_department_route_department"),
        nullable=False,
    )


class ProductRouteComponent(Base):
    __tablename__ = "product_route_component"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "appearance_id", "material_node_id", "department_node_id"],
            [
                "product_department_route.product_id",
                "product_department_route.appearance_id",
                "product_department_route.material_node_id",
                "product_department_route.department_node_id",
            ],
            name="fk_product_route_component_route",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id"],
            ["product_bom.id", "product_bom.product_id"],
            name="fk_product_route_component_bom",
        ),
        Index("idx_product_route_component_bom", "product_bom_id"),
    )

    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appearance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    material_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    department_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_bom_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
