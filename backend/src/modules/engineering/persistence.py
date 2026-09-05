from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


JSON_TYPE = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True),
    "postgresql",
)


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("factory_code", name="uq_product_factory_code"),
        CheckConstraint("version > 0", name="ck_product_version"),
        CheckConstraint("revision > 0", name="ck_product_revision"),
        ForeignKeyConstraint(
            ["id", "version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_product_current_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index("idx_product_customer", "customer_id"),
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
        BigInteger, ForeignKey("customer.id"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    factory_code: Mapped[str] = mapped_column(Text, nullable=False)
    customer_code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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
        order_by="ProductProcessFlow.product_version",
    )
    versions: Mapped[list[ProductVersion]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="ProductVersion.product_id",
        primaryjoin="Product.id == ProductVersion.product_id",
        order_by="ProductVersion.version",
    )
class ProductVersion(Base):
    __tablename__ = "product_version"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_product_version_number"),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    product: Mapped[Product] = relationship(
        back_populates="versions",
        foreign_keys=[product_id],
        primaryjoin="Product.id == ProductVersion.product_id",
    )


class ProductBom(Base):
    __tablename__ = "product_bom"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_product_bom_version",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id",
            "product_id",
            "product_version",
            name="uq_product_bom_id_version",
        ),
        UniqueConstraint(
            "product_id", "product_version", "part_no", name="uq_product_bom_part_no"
        ),
        UniqueConstraint(
            "product_id",
            "product_version",
            "sort_order",
            name="uq_product_bom_sort_order",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("product_version > 0", name="ck_product_bom_version"),
        CheckConstraint("pcs > 0", name="ck_product_bom_pcs"),
        CheckConstraint("sort_order > 0", name="ck_product_bom_sort_order"),
        Index(
            "idx_product_bom_part_name_trgm",
            "part_name",
            postgresql_using="gin",
            postgresql_ops={"part_name": "gin_trgm_ops"},
        ),
        Index(
            "idx_product_bom_part_no_trgm",
            "part_no",
            postgresql_using="gin",
            postgresql_ops={"part_no": "gin_trgm_ops"},
        ),
        Index("idx_product_bom_product", "product_id", "sort_order"),
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
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_product_process_flow_version",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "product_id", "product_version", name="uq_product_process_flow_version"
        ),
        CheckConstraint("product_version > 0", name="ck_process_flow_version"),
        CheckConstraint(
            "jsonb_typeof(flow_json) = 'object'",
            name="ck_process_flow_json_object",
        ),
        CheckConstraint(
            "flow_json ? 'schema_version'",
            name="ck_process_flow_schema_version_present",
        ),
        CheckConstraint(
            "jsonb_typeof(flow_json->'schema_version') = 'number'",
            name="ck_process_flow_schema_version_type",
        ),
        CheckConstraint(
            "flow_json->>'schema_version' = '5'",
            name="ck_process_flow_schema_version",
        ),
        CheckConstraint("flow_json ? 'nodes'", name="ck_process_flow_nodes_present"),
        CheckConstraint(
            "jsonb_typeof(flow_json->'nodes') = 'array'",
            name="ck_process_flow_nodes_type",
        ),
        CheckConstraint("flow_json ? 'edges'", name="ck_process_flow_edges_present"),
        CheckConstraint(
            "jsonb_typeof(flow_json->'edges') = 'array'",
            name="ck_process_flow_edges_type",
        ),
        CheckConstraint(
            "draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json) = 'object'",
            name="ck_process_flow_draft_object",
        ),
        CheckConstraint(
            "draft_flow_json IS NULL OR draft_flow_json->>'schema_version' = '5'",
            name="ck_process_flow_draft_schema_version",
        ),
        CheckConstraint(
            "draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'nodes') = 'array'",
            name="ck_process_flow_draft_nodes",
        ),
        CheckConstraint(
            "draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'edges') = 'array'",
            name="ck_process_flow_draft_edges",
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
        default=lambda: {"schema_version": 5, "nodes": [], "edges": []},
        server_default=text("'{\"schema_version\": 5, \"nodes\": [], \"edges\": []}'"),
    )
    draft_flow_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_TYPE,
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


class ProductRouteTask(Base):
    __tablename__ = "product_route_task"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_product_route_task_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id", "product_version"],
            ["product_bom.id", "product_bom.product_id", "product_bom.product_version"],
            name="fk_product_route_task_bom_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workshop_id", "department_id"],
            ["workshop.id", "workshop.department_id"],
            name="fk_product_route_task_workshop_department",
        ),
        CheckConstraint(
            "origin_node_type IN ('part', 'assembly')",
            name="ck_product_route_task_origin_type",
        ),
        CheckConstraint(
            "(origin_node_type = 'part' AND product_bom_id IS NOT NULL) OR "
            "(origin_node_type = 'assembly' AND product_bom_id IS NULL)",
            name="ck_product_route_task_origin_scope",
        ),
        CheckConstraint(
            "route_node_type IN ('process', 'assembly', 'supplier_processing')",
            name="ck_product_route_task_node_type",
        ),
        CheckConstraint(
            "(route_node_type IN ('process', 'assembly') "
            "AND workshop_id IS NOT NULL) OR "
            "(route_node_type = 'supplier_processing' "
            "AND workshop_id IS NULL AND origin_node_type = 'part')",
            name="ck_product_route_task_execution_scope",
        ),
        CheckConstraint("route_order >= 0", name="ck_product_route_task_order"),
        UniqueConstraint(
            "product_id", "product_version", "origin_flow_node_id", "route_flow_node_id",
            name="uq_product_route_task_origin_node",
        ),
        Index(
            "idx_product_route_task_department_page",
            "department_id", "product_id", "product_version", "origin_flow_node_id", "route_order",
        ),
        Index(
            "idx_product_route_task_workshop",
            "workshop_id", "product_id", "product_version",
        ),
        Index(
            "idx_product_route_task_item_code_trgm",
            "origin_item_code",
            postgresql_using="gin",
            postgresql_ops={"origin_item_code": "gin_trgm_ops"},
        ),
        Index(
            "idx_product_route_task_item_name_trgm",
            "origin_item_name",
            postgresql_using="gin",
            postgresql_ops={"origin_item_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    origin_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    origin_node_type: Mapped[str] = mapped_column(Text, nullable=False)
    origin_item_code: Mapped[str] = mapped_column(Text, nullable=False)
    origin_item_name: Mapped[str] = mapped_column(Text, nullable=False)
    route_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    route_node_type: Mapped[str] = mapped_column(Text, nullable=False)
    workshop_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    route_order: Mapped[int] = mapped_column(Integer, nullable=False)
