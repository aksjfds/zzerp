"""Production movement, warehouse snapshot, and undo ORM models."""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
class ProductionMovement(Base):
    __tablename__ = "production_movement"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_production_movement_quantity_positive"),
        CheckConstraint(
            "movement_type IN ('initial', 'process', 'assembly_input', "
            "'assembly_output', 'qc_qualified', 'qc_inventory', "
            "'production_inventory', 'production_inventory_restore', 'qc_rework', "
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
            "(movement_type = 'production_inventory_restore' "
            "AND source_flow_node_id IS NOT NULL AND target_flow_node_id IS NOT NULL "
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
            "(movement_type IN ('production_inventory', 'production_inventory_restore') "
            "AND warehouse_operation_id IS NOT NULL) OR "
            "(movement_type NOT IN ('production_inventory', 'production_inventory_restore') "
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


class ProductionWarehouseStorageLine(Base):
    __tablename__ = "production_warehouse_storage_line"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_operation_id",
            "original_repository_id",
            name="uq_production_warehouse_storage_line",
        ),
        CheckConstraint("quantity > 0", name="ck_production_warehouse_storage_line_quantity"),
        Index("idx_production_warehouse_storage_line_state", "processing_state_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_operation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouse_operation.id"),
        nullable=False,
    )
    original_repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
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
    department_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department.id"), nullable=False)
    source_work_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ProductionOperationUndo(Base):
    __tablename__ = "production_operation_undo"
    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('submission', 'rework_submission', 'qc_destination')",
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
