from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from database import Base
from domain.production_types import WorkOrderStatus, WorkOrderType


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


class Repository(Base):
    __tablename__ = "repository"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_repository_quantity_positive"),
        UniqueConstraint(
            "id",
            "production_item_id",
            name="uq_repository_id_production_item",
        ),
        Index("idx_repository_department", "department_id"),
        Index(
            "uq_repository_initial_position",
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "department_id",
            unique=True,
            postgresql_where=text("source_work_order_id IS NULL"),
        ),
        Index(
            "uq_repository_work_order_output",
            "source_work_order_id",
            "production_item_id",
            "flow_node_id",
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


class WorkOrder(Base):
    __tablename__ = "work_order"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_quantity_positive"),
        CheckConstraint(
            "work_order_type IN ('standard', 'assembly', 'supplier_processing')",
            name="ck_work_order_type",
        ),
        CheckConstraint(
            "supplier_name IS NULL OR "
            "(supplier_name = btrim(supplier_name) AND supplier_name <> '')",
            name="ck_work_order_supplier_name",
        ),
        CheckConstraint(
            "supplier_process_name IS NULL OR "
            "(supplier_process_name = btrim(supplier_process_name) "
            "AND supplier_process_name <> '')",
            name="ck_work_order_supplier_process_name",
        ),
        CheckConstraint(
            "completed_quantity >= 0 AND completed_quantity <= quantity",
            name="ck_work_order_completed_quantity",
        ),
        CheckConstraint(
            "processed_quantity >= completed_quantity AND processed_quantity <= quantity",
            name="ck_work_order_processed_quantity",
        ),
        CheckConstraint(
            "work_order_type <> 'supplier_processing' "
            "OR processed_quantity = completed_quantity",
            name="ck_work_order_supplier_progress",
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
            "status <> 'cancelled' OR (completed_quantity = 0 AND processed_quantity = 0)",
            name="ck_work_order_cancelled_quantity",
        ),
        CheckConstraint(
            "(status = 'open' AND completed_quantity < quantity) "
            "OR repository_id IS NULL",
            name="ck_work_order_repository_lifecycle",
        ),
        CheckConstraint(
            "(work_order_type = 'assembly' "
            "AND procedure_id IS NOT NULL "
            "AND source_flow_node_id IS NOT NULL "
            "AND supplier_name IS NULL "
            "AND supplier_process_name IS NULL) OR "
            "(work_order_type = 'standard' "
            "AND procedure_id IS NOT NULL "
            "AND source_flow_node_id IS NOT NULL "
            "AND supplier_name IS NULL "
            "AND supplier_process_name IS NULL "
            "AND (status <> 'open' OR completed_quantity = quantity "
            "OR repository_id IS NOT NULL)) OR "
            "(work_order_type = 'supplier_processing' "
            "AND procedure_id IS NULL "
            "AND is_temporary = FALSE "
            "AND repository_id IS NULL "
            "AND worker_id IS NULL "
            "AND worker_name IS NULL "
            "AND source_flow_node_id IS NOT NULL "
            "AND supplier_name IS NOT NULL "
            "AND supplier_process_name IS NOT NULL)",
            name="ck_work_order_type_source",
        ),
        ForeignKeyConstraint(
            ["repository_id", "production_item_id"],
            ["repository.id", "repository.production_item_id"],
            name="fk_work_order_repository_item",
        ),
        UniqueConstraint("work_order_no", name="uq_work_order_no"),
        Index(
            "idx_work_order_worker_activity",
            "worker_id",
            text("COALESCE(closed_at, created_at) DESC"),
            text("id DESC"),
        ),
        Index("idx_work_order_repository", "repository_id"),
        Index("idx_work_order_production_item", "production_item_id"),
        Index(
            "idx_work_order_no_trgm",
            "work_order_no",
            postgresql_using="gin",
            postgresql_ops={"work_order_no": "gin_trgm_ops"},
        ),
        Index(
            "idx_work_order_name_trgm",
            "work_order_name",
            postgresql_using="gin",
            postgresql_ops={"work_order_name": "gin_trgm_ops"},
        ),
        Index(
            "idx_work_order_repository_open",
            "repository_id",
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "idx_work_order_item_node_status",
            "production_item_id",
            "flow_node_id",
            "status",
        ),
        Index(
            "idx_work_order_open_workbench",
            "work_order_type",
            "procedure_id",
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "uq_work_order_supplier_task",
            "production_item_id",
            "flow_node_id",
            unique=True,
            postgresql_where=text("work_order_type = 'supplier_processing'"),
        ),
        Index("idx_work_order_process_position", "production_item_id", "flow_node_id", "procedure_id", text("id DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_item.id"), nullable=False
    )
    procedure_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=True
    )
    work_order_type: Mapped[WorkOrderType] = mapped_column(Text, nullable=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_process_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_order_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("worker.id"), nullable=True
    )
    worker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[WorkOrderStatus] = mapped_column(
        Text,
        nullable=False,
        default="open",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class WorkOrderMaterial(Base):
    __tablename__ = "work_order_material"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_material_quantity"),
        ForeignKeyConstraint(
            ["repository_id", "production_item_id"],
            ["repository.id", "repository.production_item_id"],
            name="fk_work_order_material_repository_item",
        ),
        Index("idx_work_order_material_production_item", "production_item_id"),
        Index("idx_work_order_material_repository", "repository_id"),
        UniqueConstraint(
            "work_order_id",
            "repository_id",
            name="uq_work_order_material_repository",
        ),
        UniqueConstraint(
            "id",
            "work_order_id",
            "production_item_id",
            name="uq_work_order_material_movement_context",
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
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_previous_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    source_work_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


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
            "destination_decided_by IS NULL OR (destination_decided_by = "
            "btrim(destination_decided_by) AND destination_decided_by <> '')",
            name="ck_batch_destination_actor",
        ),
        CheckConstraint(
            "(recorded_at IS NULL AND qualified_quantity IS NULL "
            "AND rework_quantity IS NULL AND scrap_quantity IS NULL "
            "AND lost_quantity IS NULL AND qc_worker_id IS NULL "
            "AND qc_worker_name IS NULL AND qualified_destination IS NULL "
            "AND destination_decided_at IS NULL AND destination_decided_by IS NULL) OR "
            "(recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL "
            "AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL "
            "AND lost_quantity IS NOT NULL AND qc_worker_id IS NOT NULL "
            "AND qc_worker_name IS NOT NULL "
            "AND ((qualified_quantity = 0 AND qualified_destination IS NULL "
            "AND destination_decided_at IS NULL AND destination_decided_by IS NULL) "
            "OR (qualified_quantity > 0 AND ((qualified_destination IS NULL "
            "AND destination_decided_at IS NULL AND destination_decided_by IS NULL) "
            "OR (qualified_destination IN ('return', 'release', 'inventory') "
            "AND destination_decided_at IS NOT NULL AND destination_decided_by IS NOT NULL)))) "
            "AND qualified_quantity + rework_quantity + scrap_quantity "
            "+ lost_quantity = submitted_quantity)",
            name="ck_batch_inspection_complete",
        ),
        UniqueConstraint("id", "work_order_id", name="uq_work_order_batch_id_order"),
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
            postgresql_where=text(
                "recorded_at IS NULL OR (qualified_quantity > 0 "
                "AND destination_decided_at IS NULL)"
            ),
        ),
        Index(
            "idx_work_order_batch_history",
            text("id DESC"),
            postgresql_where=text("recorded_at IS NOT NULL"),
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
    rework_source_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    qualified_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rework_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrap_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lost_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qc_worker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("worker.id"), nullable=True
    )
    qc_worker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualified_destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_decided_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    destination_decided_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class ProductionMovement(Base):
    __tablename__ = "production_movement"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_production_movement_quantity_positive"),
        CheckConstraint(
            "movement_type IN ('initial', 'process', 'assembly_input', "
            "'assembly_output', 'qc_qualified', 'qc_inventory', "
            "'production_inventory', 'qc_rework', "
            "'inventory_issue', 'assembly_input_restore', 'scrap', 'lost')",
            name="ck_production_movement_type",
        ),
        CheckConstraint(
            "(movement_type = 'initial' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NULL "
            "AND target_department_id IS NOT NULL AND work_order_id IS NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type = 'inventory_issue' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NOT NULL AND work_order_id IS NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type IN ('process', 'assembly_output') "
            "AND source_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND (target_flow_node_id IS NULL) = (target_department_id IS NULL) "
            "AND work_order_id IS NOT NULL) OR "
            "(movement_type = 'assembly_input' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NULL AND work_order_id IS NOT NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type = 'assembly_input_restore' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NOT NULL AND work_order_id IS NOT NULL "
            "AND work_order_batch_id IS NULL) OR "
            "(movement_type = 'qc_qualified' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NOT NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NOT NULL "
            "AND work_order_id IS NOT NULL AND work_order_batch_id IS NOT NULL) OR "
            "(movement_type = 'qc_inventory' AND source_flow_node_id IS NOT NULL "
            "AND target_flow_node_id IS NULL AND source_department_id IS NOT NULL "
            "AND target_department_id IS NOT NULL "
            "AND work_order_id IS NOT NULL AND work_order_batch_id IS NOT NULL) OR "
            "(movement_type = 'production_inventory' "
            "AND source_flow_node_id IS NOT NULL AND target_flow_node_id IS NULL "
            "AND source_department_id IS NOT NULL AND target_department_id IS NOT NULL "
            "AND work_order_id IS NULL AND work_order_batch_id IS NULL) OR "
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
        CheckConstraint(
            "(movement_type IN ('assembly_input', 'assembly_input_restore') "
            "AND work_order_material_id IS NOT NULL) OR "
            "(movement_type NOT IN ('assembly_input', 'assembly_input_restore') "
            "AND work_order_material_id IS NULL)",
            name="ck_production_movement_assembly_material",
        ),
        CheckConstraint(
            "(movement_type = 'production_inventory' "
            "AND warehouse_operation_id IS NOT NULL) OR "
            "(movement_type <> 'production_inventory' "
            "AND warehouse_operation_id IS NULL)",
            name="ck_production_movement_warehouse_operation",
        ),
        ForeignKeyConstraint(
            ["work_order_batch_id", "work_order_id"],
            ["work_order_batch.id", "work_order_batch.work_order_id"],
            name="fk_production_movement_batch_order",
        ),
        ForeignKeyConstraint(
            ["work_order_material_id", "work_order_id", "production_item_id"],
            [
                "work_order_material.id",
                "work_order_material.work_order_id",
                "work_order_material.production_item_id",
            ],
            name="fk_production_movement_assembly_material_context",
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
                "('process', 'assembly_output')"
            ),
        ),
        Index(
            "uq_production_movement_batch_qualified_destination",
            "work_order_batch_id",
            unique=True,
            postgresql_where=text(
                "work_order_batch_id IS NOT NULL AND movement_type IN "
                "('qc_qualified', 'qc_inventory')"
            ),
        ),
        Index(
            "uq_production_movement_assembly_input",
            "work_order_material_id",
            unique=True,
            postgresql_where=text("movement_type = 'assembly_input'"),
        ),
        Index(
            "uq_production_movement_warehouse_operation",
            "warehouse_operation_id",
            unique=True,
            postgresql_where=text("warehouse_operation_id IS NOT NULL"),
        ),
        Index(
            "idx_production_movement_assembly_material",
            "work_order_material_id",
            postgresql_where=text("work_order_material_id IS NOT NULL"),
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
    work_order_material_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    warehouse_operation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("warehouse_operation.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ProductionOperationUndo(Base):
    __tablename__ = "production_operation_undo"
    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('submission', 'rework_submission')",
            name="ck_production_operation_undo_type",
        ),
        CheckConstraint(
            "status IN ('applied', 'reversed')",
            name="ck_production_operation_undo_status",
        ),
        CheckConstraint(
            "(status = 'applied' AND reversed_at IS NULL AND reversed_by IS NULL) OR "
            "(status = 'reversed' AND reversed_at IS NOT NULL AND reversed_by IS NOT NULL)",
            name="ck_production_operation_undo_reversed",
        ),
        Index(
            "idx_production_operation_undo_order",
            "work_order_id",
            text("id DESC"),
        ),
        Index(
            "idx_production_operation_undo_active",
            "work_order_id",
            text("id DESC"),
            postgresql_where=text("status = 'applied'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    work_order_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    operation_label: Mapped[str] = mapped_column(Text, nullable=False)
    department_code: Mapped[str] = mapped_column(Text, nullable=False)
    actor_username: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="applied")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    reversed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
