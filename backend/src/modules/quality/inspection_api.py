"""Transaction-aware inspection contexts for collaborating modules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.quality.context_api import InspectionBatchContext
from modules.quality.persistence import WorkOrderBatch


def load_inspection_batch(
    session: Session,
    batch_id: int,
    *,
    for_update: bool = False,
) -> InspectionBatchContext | None:
    return session.get(
        WorkOrderBatch,
        batch_id,
        with_for_update=for_update,
    )


def list_inspection_batches(
    session: Session,
    work_order_id: int,
) -> list[InspectionBatchContext]:
    return list(
        session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id == work_order_id
            )
        ).all()
    )


__all__ = ["list_inspection_batches", "load_inspection_batch"]
