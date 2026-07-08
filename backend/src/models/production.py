from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_order_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_bom_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("product_bom.id"), nullable=True
    )
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


class WorkOrder(Base):
    __tablename__ = "work_order"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_quantity_positive"),
        CheckConstraint(
            "completed_quantity >= 0 AND completed_quantity <= quantity",
            name="ck_work_order_completed_quantity",
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')",
            name="ck_work_order_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    repository_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("repository.id", ondelete="SET NULL"), nullable=True
    )
    production_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_item.id"), nullable=False
    )
    procedure_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=True
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
    worker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("worker.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


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
            "AND lost_quantity IS NULL AND qc_worker_name IS NULL) OR "
            "(recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL "
            "AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL "
            "AND lost_quantity IS NOT NULL AND qc_worker_name IS NOT NULL "
            "AND qualified_quantity + rework_quantity + scrap_quantity "
            "+ lost_quantity = submitted_quantity)",
            name="ck_batch_inspection_complete",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    submitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rework_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrap_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lost_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qc_worker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class WorkOrderMaterial(Base):
    __tablename__ = "work_order_material"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_order_material_quantity"),
        Index(
            "idx_work_order_material_production_item",
            "production_item_id",
        ),
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
    repository_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("repository.id", ondelete="SET NULL"), nullable=True
    )
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
            "'assembly_output', 'qc_qualified', 'qc_rework', 'scrap', 'lost')",
            name="ck_production_movement_type",
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
        Index("idx_production_movement_work_order", "work_order_id"),
        Index("idx_production_movement_batch", "work_order_batch_id"),
        Index("idx_production_movement_target_node", "target_flow_node_id"),
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
        BigInteger, ForeignKey("work_order.id", ondelete="SET NULL"), nullable=True
    )
    work_order_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("work_order_batch.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
