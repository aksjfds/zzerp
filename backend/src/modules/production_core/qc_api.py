"""Production-core batch and work-order operations required by quality."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.time import utc_now

from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
)


def load_qc_work_order(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> WorkOrderContext | None:
    return session.get(WorkOrder, work_order_id, with_for_update=for_update)


def load_qc_production_item(
    session: Session,
    production_item_id: int,
    *,
    for_update: bool = False,
) -> ProductionItemContext | None:
    return session.get(
        ProductionItem,
        production_item_id,
        with_for_update=for_update,
    )


def load_qc_batch(
    session: Session,
    batch_id: int,
    *,
    for_update: bool = False,
):
    return session.get(WorkOrderBatch, batch_id, with_for_update=for_update)


def list_qc_batches(session: Session, work_order_id: int):
    return list(
        session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id == work_order_id
            )
        )
    )


def rework_submitted_quantity(
    session: Session,
    work_order_id: int,
    source_batch_id: int,
) -> int:
    return int(
        session.scalar(
            select(
                func.coalesce(func.sum(WorkOrderBatch.submitted_quantity), 0)
            ).where(
                WorkOrderBatch.work_order_id == work_order_id,
                WorkOrderBatch.rework_source_batch_id == source_batch_id,
            )
        )
        or 0
    )


def create_qc_batch(
    session: Session,
    *,
    work_order_id: int,
    submitted_quantity: int,
    source_flow_node_id: str,
    rework_source_batch_id: int | None,
):
    batch = WorkOrderBatch(
        work_order_id=work_order_id,
        submitted_quantity=submitted_quantity,
        source_flow_node_id=source_flow_node_id,
        rework_source_batch_id=rework_source_batch_id,
    )
    session.add(batch)
    session.flush()
    return batch


def record_qc_batch_result(
    batch,
    *,
    qualified_quantity: int,
    rework_quantity: int,
    scrap_quantity: int,
    lost_quantity: int,
    qc_worker_id: int,
    qc_worker_name: str,
    defect_reason: str | None,
) -> None:
    batch.qualified_quantity = qualified_quantity
    batch.rework_quantity = rework_quantity
    batch.scrap_quantity = scrap_quantity
    batch.lost_quantity = lost_quantity
    batch.qc_worker_id = qc_worker_id
    batch.qc_worker_name = qc_worker_name
    batch.defect_reason = defect_reason
    batch.recorded_at = utc_now()


def record_qc_batch_destination(
    batch,
    *,
    destination: str,
    actor_username: str,
) -> None:
    batch.qualified_destination = destination
    batch.destination_decided_at = utc_now()
    batch.destination_decided_by = actor_username


__all__ = [
    "create_qc_batch",
    "list_qc_batches",
    "load_qc_batch",
    "load_qc_production_item",
    "load_qc_work_order",
    "record_qc_batch_result",
    "record_qc_batch_destination",
    "rework_submitted_quantity",
]
