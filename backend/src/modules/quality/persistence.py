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
