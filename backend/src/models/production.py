from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
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
        Index("idx_production_item_order_item", "customer_order_item_id"),
        Index("idx_production_item_bom", "product_bom_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    origin_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)


class Repository(Base):
    __tablename__ = "repository"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_repository_quantity_positive"),
        UniqueConstraint(
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "department_id",
            name="uq_repository_position",
        ),
        UniqueConstraint(
            "id",
            "production_item_id",
            name="uq_repository_id_production_item",
        ),
        Index("idx_repository_department", "department_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class ProcedureTagStock(Base):
    __tablename__ = "procedure_tag_stock"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_procedure_tag_stock_quantity_positive",
        ),
        UniqueConstraint(
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "department_id",
            "tag_set_id",
            name="uq_procedure_tag_stock_position",
        ),
        UniqueConstraint(
            "id",
            "production_item_id",
            name="uq_procedure_tag_stock_id_production_item",
        ),
        Index(
            "idx_procedure_tag_stock_department",
            "department_id",
            "tag_set_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    tag_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkOrder(Base):
    __tablename__ = "work_order"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_quantity_positive"),
        CheckConstraint(
            "work_order_type IN ('tag', 'purchase_receipt', 'assembly')",
            name="ck_work_order_type",
        ),
        CheckConstraint(
            "completed_quantity >= 0 AND completed_quantity <= quantity",
            name="ck_work_order_completed_quantity",
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')",
            name="ck_work_order_status",
        ),
        CheckConstraint(
            "(status = 'open' AND closed_at IS NULL) OR "
            "(status IN ('closed', 'cancelled') AND closed_at IS NOT NULL)",
            name="ck_work_order_closed_at",
        ),
        CheckConstraint(
            "status <> 'closed' OR completed_quantity = quantity",
            name="ck_work_order_closed_quantity",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR completed_quantity = 0",
            name="ck_work_order_cancelled_quantity",
        ),
        CheckConstraint(
            "(work_order_type = 'assembly' AND procedure_id IS NULL "
            "AND applied_tag_set_id IS NULL "
            "AND source_tag_set_id IS NULL AND target_tag_set_id IS NULL "
            "AND source_flow_node_id IS NULL "
            "AND repository_id IS NULL AND procedure_tag_stock_id IS NULL) OR "
            "(work_order_type = 'tag' AND procedure_id IS NOT NULL "
            "AND applied_tag_set_id IS NOT NULL "
            "AND target_tag_set_id IS NOT NULL "
            "AND source_flow_node_id IS NOT NULL "
            "AND (repository_id IS NULL OR procedure_tag_stock_id IS NULL) "
            "AND (status <> 'open' OR completed_quantity = quantity "
            "OR repository_id IS NOT NULL "
            "OR procedure_tag_stock_id IS NOT NULL)) OR "
            "(work_order_type = 'purchase_receipt' AND procedure_id IS NOT NULL "
            "AND applied_tag_set_id IS NULL "
            "AND source_tag_set_id IS NULL AND target_tag_set_id IS NULL "
            "AND source_flow_node_id IS NOT NULL "
            "AND procedure_tag_stock_id IS NULL "
            "AND (status <> 'open' OR repository_id IS NOT NULL))",
            name="ck_work_order_type_source",
        ),
        ForeignKeyConstraint(
            ["repository_id", "production_item_id"],
            ["repository.id", "repository.production_item_id"],
            name="fk_work_order_repository_item",
        ),
        ForeignKeyConstraint(
            ["procedure_tag_stock_id", "production_item_id"],
            ["procedure_tag_stock.id", "procedure_tag_stock.production_item_id"],
            name="fk_work_order_tag_stock_item",
        ),
        Index(
            "idx_work_order_worker_activity",
            "worker_id",
            text("COALESCE(closed_at, created_at) DESC"),
            text("id DESC"),
        ),
        Index("idx_work_order_applied_tag_set", "applied_tag_set_id", text("id DESC")),
        Index("idx_work_order_repository", "repository_id"),
        Index("idx_work_order_tag_stock", "procedure_tag_stock_id"),
        Index("idx_work_order_production_item", "production_item_id"),
        Index(
            "idx_work_order_repository_open",
            "repository_id",
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "idx_work_order_tag_stock_open",
            "procedure_tag_stock_id",
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "idx_work_order_item_node_status",
            "production_item_id",
            "flow_node_id",
            "status",
        ),
        Index(
            "idx_work_order_tag_position",
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "target_tag_set_id",
            text("id DESC"),
            postgresql_where=text("work_order_type = 'tag'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    procedure_tag_stock_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    production_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_item.id"), nullable=False
    )
    procedure_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=True
    )
    applied_tag_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=True
    )
    source_tag_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=True
    )
    target_tag_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=True
    )
    work_order_type: Mapped[str] = mapped_column(Text, nullable=False)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_order_name: Mapped[str] = mapped_column(Text, nullable=False)
    worker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("worker.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class WorkOrderBatch(Base):
    __tablename__ = "work_order_batch"
    __table_args__ = (
        CheckConstraint("submitted_quantity > 0", name="ck_batch_submitted_positive"),
        CheckConstraint(
            "qualified_quantity IS NULL OR qualified_quantity >= 0",
            name="ck_batch_qualified",
        ),
        CheckConstraint(
            "rework_quantity IS NULL OR rework_quantity >= 0",
            name="ck_batch_rework",
        ),
        CheckConstraint(
            "scrap_quantity IS NULL OR scrap_quantity >= 0",
            name="ck_batch_scrap",
        ),
        CheckConstraint(
            "lost_quantity IS NULL OR lost_quantity >= 0",
            name="ck_batch_lost",
        ),
        CheckConstraint(
            "(recorded_at IS NULL AND qualified_quantity IS NULL "
            "AND rework_quantity IS NULL AND scrap_quantity IS NULL "
            "AND lost_quantity IS NULL AND qc_worker_id IS NULL "
            "AND qc_worker_name IS NULL) OR "
            "(recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL "
            "AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL "
            "AND lost_quantity IS NOT NULL AND qc_worker_id IS NOT NULL "
            "AND qc_worker_name IS NOT NULL "
            "AND qualified_quantity + rework_quantity + scrap_quantity "
            "+ lost_quantity = submitted_quantity)",
            name="ck_batch_inspection_complete",
        ),
        UniqueConstraint(
            "id",
            "work_order_id",
            name="uq_work_order_batch_id_order",
        ),
        ForeignKeyConstraint(
            ["rework_source_batch_id", "work_order_id"],
            ["work_order_batch.id", "work_order_batch.work_order_id"],
            name="fk_work_order_batch_rework_source",
        ),
        Index("idx_work_order_batch_order", "work_order_id"),
        Index("idx_work_order_batch_rework_source", "rework_source_batch_id"),
        Index(
            "idx_work_order_batch_pending",
            text("id DESC"),
            "work_order_id",
            postgresql_where=text("recorded_at IS NULL"),
        ),
        Index(
            "idx_work_order_batch_qc_worker_recorded",
            "qc_worker_id",
            text("recorded_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    submitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    rework_source_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    qualified_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rework_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrap_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lost_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qc_worker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("worker.id"), nullable=True
    )
    qc_worker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


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


class ProductionMovement(Base):
    __tablename__ = "production_movement"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_production_movement_quantity_positive"),
        CheckConstraint(
            "movement_type IN ('initial', 'process', 'assembly_input', "
            "'assembly_output', 'purchase_receipt', 'qc_qualified', 'qc_rework', "
            "'procedure_dispatch', 'scrap', 'lost')",
            name="ck_production_movement_type",
        ),
        CheckConstraint(
            "(movement_type = 'initial' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NULL "
            "AND target_department_id IS NOT NULL AND work_order_id IS NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type = 'procedure_dispatch' "
            "AND source_flow_node_id IS NOT NULL "
            "AND source_department_id IS NOT NULL "
            "AND (target_flow_node_id IS NULL) = (target_department_id IS NULL) "
            "AND work_order_id IS NULL AND work_order_batch_id IS NULL) OR "
            "(movement_type IN ('process', 'purchase_receipt', 'assembly_output') "
            "AND source_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND (target_flow_node_id IS NULL) = (target_department_id IS NULL) "
            "AND work_order_id IS NOT NULL) OR "
            "(movement_type = 'assembly_input' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NULL AND work_order_id IS NOT NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type = 'qc_qualified' AND source_flow_node_id IS NOT NULL "
            "AND source_department_id IS NOT NULL "
            "AND (target_flow_node_id IS NULL) = (target_department_id IS NULL) "
            "AND work_order_id IS NOT NULL AND work_order_batch_id IS NOT NULL) OR "
            "(movement_type = 'qc_rework' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NOT NULL "
            "AND work_order_id IS NOT NULL AND work_order_batch_id IS NOT NULL) OR "
            "(movement_type IN ('scrap', 'lost') AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NULL AND work_order_id IS NOT NULL "
            "AND work_order_batch_id IS NOT NULL)",
            name="ck_production_movement_context",
        ),
        ForeignKeyConstraint(
            ["work_order_batch_id", "work_order_id"],
            ["work_order_batch.id", "work_order_batch.work_order_id"],
            name="fk_production_movement_batch_order",
        ),
        Index(
            "idx_production_movement_item_created",
            "production_item_id",
            "created_at",
        ),
        Index(
            "idx_production_movement_target_department_created",
            "target_department_id",
            "created_at",
        ),
        Index(
            "idx_production_movement_work_order",
            "work_order_id",
            "id",
            postgresql_where=text("work_order_id IS NOT NULL"),
        ),
        Index(
            "idx_production_movement_batch",
            "work_order_batch_id",
            "id",
            postgresql_where=text("work_order_batch_id IS NOT NULL"),
        ),
        Index(
            "uq_production_movement_batch_submission",
            "work_order_batch_id",
            unique=True,
            postgresql_where=text(
                "work_order_batch_id IS NOT NULL AND movement_type IN "
                "('process', 'purchase_receipt', 'assembly_output')"
            ),
        ),
        Index(
            "uq_production_movement_assembly_input",
            "work_order_id",
            "production_item_id",
            unique=True,
            postgresql_where=text("movement_type = 'assembly_input'"),
        ),
        Index(
            "idx_production_movement_source_department",
            "source_department_id",
            postgresql_where=text("source_department_id IS NOT NULL"),
        ),
        Index(
            "idx_production_movement_position_latest",
            "target_department_id",
            "production_item_id",
            "target_flow_node_id",
            "source_flow_node_id",
            "source_tag_set_id",
            "target_tag_set_id",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("target_department_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_item.id", ondelete="CASCADE"), nullable=False
    )
    source_flow_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_flow_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tag_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=True
    )
    target_tag_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=True
    )
    source_department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=True
    )
    target_department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(Text, nullable=False)
    work_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("work_order.id"), nullable=True
    )
    work_order_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
