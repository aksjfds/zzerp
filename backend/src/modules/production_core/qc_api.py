"""Production-core batch and work-order operations required by quality."""

from collections.abc import Iterable

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from domain.production_types import (
    WORK_ORDER_STATUS_CLOSED,
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_SUPPLIER_PROCESSING,
)
from domain.time import utc_now
from modules.errors import DomainError

from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.work_order_progress import (
    calculate_supplier_processing_qc_progress,
    validate_supplier_processing_work_order_progress,
)


def load_qc_work_order(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> WorkOrderContext | None:
    return session.get(
        WorkOrder,
        work_order_id,
        with_for_update=for_update,
        populate_existing=for_update,
    )


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
        populate_existing=for_update,
    )


def load_qc_batch(
    session: Session,
    batch_id: int,
    *,
    for_update: bool = False,
):
    return session.get(
        WorkOrderBatch,
        batch_id,
        with_for_update=for_update,
        populate_existing=for_update,
    )


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


def undo_qc_batch_result(session: Session, batch_id: int) -> None:
    batch = load_qc_batch(session, batch_id)
    if batch is None:
        raise DomainError("qc_batch_not_found", "质检批次不存在", status_code=404)
    order = load_qc_work_order(session, batch.work_order_id, for_update=True)
    batch = load_qc_batch(session, batch_id, for_update=True)
    if order is None or batch is None or batch.work_order_id != order.id:
        raise DomainError("qc_batch_not_found", "质检批次不存在", status_code=404)
    if batch.recorded_at is None:
        raise DomainError(
            "qc_result_not_recorded",
            "当前批次尚未录入质检结果",
            status_code=409,
        )
    if batch.destination_decided_at is not None or batch.qualified_destination is not None:
        raise DomainError(
            "qc_destination_decided",
            "合格品去向已经确定，不能撤回质检",
            status_code=409,
        )

    child_batches = list(session.scalars(
        select(WorkOrderBatch)
        .where(
            WorkOrderBatch.work_order_id == order.id,
            WorkOrderBatch.rework_source_batch_id == batch.id,
        )
        .with_for_update()
    ))
    if child_batches:
        raise DomainError(
            "qc_rework_already_submitted",
            "该结果已经产生返工复检，不能撤回",
            status_code=409,
        )

    movements = list(session.scalars(
        select(ProductionMovement)
        .where(ProductionMovement.work_order_batch_id == batch.id)
        .with_for_update()
    ))
    result_movement_types = {"qc_rework", "scrap", "lost"}
    submission_movement_types = {"process", "assembly_output"}
    if any(
        movement.movement_type
        not in result_movement_types | submission_movement_types
        for movement in movements
    ):
        raise DomainError(
            "qc_result_already_used",
            "该质检结果已经产生后续流转，不能撤回",
            status_code=409,
        )

    if order.work_order_type == WORK_ORDER_SUPPLIER_PROCESSING:
        if movements:
            raise DomainError(
                "qc_result_already_used",
                "该委外质检结果已经产生后续流转，不能撤回",
                status_code=409,
            )
        session.delete(batch)
        session.flush()
        return

    session.execute(
        text("SELECT set_config('zzerp.qc_inspection_undo_batch_id', :batch_id, true)"),
        {"batch_id": str(batch.id)},
    )
    for movement in movements:
        if movement.movement_type in result_movement_types:
            session.delete(movement)
    session.flush()
    batch.qualified_quantity = None
    batch.rework_quantity = None
    batch.scrap_quantity = None
    batch.lost_quantity = None
    batch.qc_worker_id = None
    batch.qc_worker_name = None
    batch.defect_reason = None
    batch.recorded_at = None
    if order.status == WORK_ORDER_STATUS_CLOSED:
        order.status = WORK_ORDER_STATUS_OPEN
        order.closed_at = None
    session.flush()


def refresh_supplier_processing_release_progress(
    order: WorkOrderContext,
    batches: Iterable[InspectionBatchContext],
) -> bool:
    """Synchronize supplier-order progress from released QC batches."""
    if order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError(
            "supplier_processing_work_order_required",
            "当前工单不是委外加工工单",
            status_code=409,
        )
    progress = calculate_supplier_processing_qc_progress(order, batches)
    released_quantity = progress.released_quantity
    order.processed_quantity = released_quantity
    order.completed_quantity = released_quantity
    if released_quantity == order.quantity:
        order.status = WORK_ORDER_STATUS_CLOSED
        order.closed_at = utc_now()
        validate_supplier_processing_work_order_progress(order, progress)
        return True
    if order.status != WORK_ORDER_STATUS_OPEN:
        raise DomainError(
            "supplier_processing_work_order_closed",
            "委外加工工单已经结单",
            status_code=409,
        )
    validate_supplier_processing_work_order_progress(order, progress)
    return False


__all__ = [
    "create_qc_batch",
    "list_qc_batches",
    "load_qc_batch",
    "load_qc_production_item",
    "load_qc_work_order",
    "record_qc_batch_result",
    "record_qc_batch_destination",
    "refresh_supplier_processing_release_progress",
    "rework_submitted_quantity",
    "undo_qc_batch_result",
]
