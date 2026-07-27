"""Immutable quality projections used by workforce reporting."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.quality.persistence import WorkOrderBatch


@dataclass(frozen=True, slots=True)
class WorkOrderBatchActivity:
    id: int
    work_order_id: int
    submitted_quantity: int
    rework_source_batch_id: int | None
    qualified_quantity: int | None
    rework_quantity: int | None
    scrap_quantity: int | None
    lost_quantity: int | None
    qc_worker_id: int | None
    recorded_at: datetime | None


def _batch_activity(batch: WorkOrderBatch) -> WorkOrderBatchActivity:
    return WorkOrderBatchActivity(
        id=batch.id,
        work_order_id=batch.work_order_id,
        submitted_quantity=batch.submitted_quantity,
        rework_source_batch_id=batch.rework_source_batch_id,
        qualified_quantity=batch.qualified_quantity,
        rework_quantity=batch.rework_quantity,
        scrap_quantity=batch.scrap_quantity,
        lost_quantity=batch.lost_quantity,
        qc_worker_id=batch.qc_worker_id,
        recorded_at=batch.recorded_at,
    )


def list_qc_worker_order_ids(
    session: Session,
    worker_id: int,
    month_start: datetime,
    month_end: datetime,
) -> frozenset[int]:
    return frozenset(
        session.scalars(
            select(WorkOrderBatch.work_order_id)
            .where(
                WorkOrderBatch.qc_worker_id == worker_id,
                WorkOrderBatch.recorded_at >= month_start,
                WorkOrderBatch.recorded_at < month_end,
            )
            .distinct()
        ).all()
    )


def list_qualified_batch_order_ids(
    session: Session,
    month_start: datetime,
    month_end: datetime,
) -> frozenset[int]:
    """Return only orders that produced qualified quantity in the month."""
    return frozenset(
        session.scalars(
            select(WorkOrderBatch.work_order_id)
            .where(
                WorkOrderBatch.recorded_at >= month_start,
                WorkOrderBatch.recorded_at < month_end,
                WorkOrderBatch.qualified_quantity > 0,
            )
            .distinct()
        ).all()
    )


def list_batch_activities(
    session: Session,
    work_order_ids: Collection[int],
    *,
    month_start: datetime | None = None,
    month_end: datetime | None = None,
    qualified_only: bool = False,
) -> list[WorkOrderBatchActivity]:
    if not work_order_ids:
        return []
    statement = select(WorkOrderBatch).where(
        WorkOrderBatch.work_order_id.in_(work_order_ids)
    )
    if month_start is not None:
        statement = statement.where(WorkOrderBatch.recorded_at >= month_start)
    if month_end is not None:
        statement = statement.where(WorkOrderBatch.recorded_at < month_end)
    if qualified_only:
        statement = statement.where(WorkOrderBatch.qualified_quantity > 0)
    batches = session.scalars(
        statement.order_by(
            WorkOrderBatch.recorded_at.desc(),
            WorkOrderBatch.id.desc(),
        )
    ).all()
    return [_batch_activity(batch) for batch in batches]


__all__ = [
    "WorkOrderBatchActivity",
    "list_batch_activities",
    "list_qualified_batch_order_ids",
    "list_qc_worker_order_ids",
]
