"""Transaction-aware inspection contexts for collaborating modules."""

from sqlalchemy.orm import Session

from modules.production_core.context_api import InspectionBatchContext
from modules.production_core.qc_api import list_qc_batches, load_qc_batch


def load_inspection_batch(
    session: Session,
    batch_id: int,
    *,
    for_update: bool = False,
) -> InspectionBatchContext | None:
    return load_qc_batch(session, batch_id, for_update=for_update)


def list_inspection_batches(
    session: Session,
    work_order_id: int,
) -> list[InspectionBatchContext]:
    return list_qc_batches(session, work_order_id)


__all__ = ["list_inspection_batches", "load_inspection_batch"]
