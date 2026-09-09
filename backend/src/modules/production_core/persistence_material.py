"""Production material identity, processing state, and position ORM models."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
class ProductionItem(Base):
    __tablename__ = "production_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_order_item_id", "product_id", "product_version"],
            [
                "customer_order_item.id",
                "customer_order_item.product_id",
                "customer_order_item.product_version",
            ],
            name="fk_production_item_order_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id", "product_version"],
            [
                "product_bom.id",
                "product_bom.product_id",
                "product_bom.product_version",
            ],
            name="fk_production_item_bom_version",
        ),
        CheckConstraint("product_version > 0", name="ck_production_item_version"),
        UniqueConstraint(
            "id",
            "customer_order_item_id",
            "product_id",
            "product_version",
            name="uq_production_item_context",
        ),
        Index("idx_production_item_order_item", "customer_order_item_id"),
        Index("idx_production_item_bom", "product_bom_id"),
        Index(
            "uq_production_item_part_origin",
            "customer_order_item_id",
            "product_bom_id",
            "origin_flow_node_id",
            unique=True,
            postgresql_where=text("product_bom_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    origin_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)


class MaterialProcessingState(Base):
    __tablename__ = "material_processing_state"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_material_processing_state_product_version",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id", "product_version"],
            ["product_bom.id", "product_bom.product_id", "product_bom.product_version"],
            name="fk_material_processing_state_bom_version",
        ),
        CheckConstraint("product_version > 0", name="ck_material_processing_state_version"),
        CheckConstraint(
            "item_type IN ('part', 'assembly')",
            name="ck_material_processing_state_item_type",
        ),
        CheckConstraint(
            "(item_type = 'part' AND product_bom_id IS NOT NULL) OR "
            "(item_type = 'assembly' AND product_bom_id IS NULL)",
            name="ck_material_processing_state_material",
        ),
        CheckConstraint(
            "qc_status IN ('none', 'returned', 'released', 'stored')",
            name="ck_material_processing_state_qc_status",
        ),
        CheckConstraint(
            "display_text = btrim(display_text) AND display_text <> ''",
            name="ck_material_processing_state_display",
        ),
        CheckConstraint(
            "origin_flow_node_id = btrim(origin_flow_node_id) AND origin_flow_node_id <> '' "
            "AND completed_flow_node_id = btrim(completed_flow_node_id) AND completed_flow_node_id <> '' "
            "AND resume_flow_node_id = btrim(resume_flow_node_id) AND resume_flow_node_id <> ''",
            name="ck_material_processing_state_nodes",
        ),
        CheckConstraint(
            "jsonb_typeof(procedure_history) = 'array'",
            name="ck_material_processing_state_history",
        ),
        CheckConstraint(
            "length(state_signature) = 64",
            name="ck_material_processing_state_signature",
        ),
        UniqueConstraint("state_signature", name="uq_material_processing_state_signature"),
        UniqueConstraint(
            "id", "product_id", "product_version",
            name="uq_material_processing_state_context",
        ),
        Index(
            "idx_material_processing_state_lookup",
            "product_id", "product_version", "item_type", "product_bom_id",
            "origin_flow_node_id", "display_text",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    origin_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    completed_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    resume_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    qc_status: Mapped[str] = mapped_column(Text, nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    state_signature: Mapped[str] = mapped_column(String(64), nullable=False)


class Repository(Base):
    __tablename__ = "repository"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_repository_quantity_positive"),
        UniqueConstraint(
            "id",
            "production_item_id",
            name="uq_repository_id_production_item",
        ),
        UniqueConstraint(
            "id",
            "production_item_id",
            "processing_state_id",
            name="uq_repository_source_context",
        ),
        Index("idx_repository_department", "department_id"),
        Index("idx_repository_processing_state", "processing_state_id"),
        Index(
            "uq_repository_initial_position",
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "department_id",
            "processing_state_id",
            unique=True,
            postgresql_where=text("source_work_order_id IS NULL"),
        ),
        Index(
            "uq_repository_work_order_output",
            "source_work_order_id",
            "production_item_id",
            "flow_node_id",
            "processing_state_id",
            unique=True,
            postgresql_where=text("source_work_order_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    processing_state_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_processing_state.id"),
        nullable=False,
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    source_work_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id", use_alter=True, name="fk_repository_source_work_order"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

