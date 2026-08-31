"""Authoritative work-order stage and source-reservation projections."""

from sqlalchemy import func, select

from modules.production_core.persistence import (
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.work_order_progress import (
    calculate_work_order_progress,
    order_remaining_expression,
)


def work_order_stage(order: WorkOrder, batches: list[WorkOrderBatch]) -> str:
    if order.status != "open":
        return "completed"
    progress = calculate_work_order_progress(order, batches)
    if progress.rework_pending_quantity > 0:
        return "rework"
    if progress.pending_qc_quantity > 0:
        return "qc"
    if progress.initial_processing_quantity > 0:
        return "processing"
    if progress.ready_for_qc_quantity > 0:
        return "processing_completed"
    return "processing"


def reserved_quantities(session, repository_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    if not repository_ids:
        return result
    for repository_id, quantity in session.execute(
        select(
            WorkOrder.repository_id,
            func.sum(order_remaining_expression()),
        )
        .where(
            WorkOrder.repository_id.in_(repository_ids),
            WorkOrder.status == "open",
        )
        .group_by(WorkOrder.repository_id)
    ):
        result[repository_id] = quantity
    for repository_id, quantity in session.execute(
        select(
            WorkOrderMaterial.repository_id,
            func.sum(WorkOrderMaterial.quantity),
        )
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
        .where(
            WorkOrderMaterial.repository_id.in_(repository_ids),
            WorkOrder.status == "open",
        )
        .group_by(WorkOrderMaterial.repository_id)
    ):
        result[repository_id] = result.get(repository_id, 0) + quantity
    return result
