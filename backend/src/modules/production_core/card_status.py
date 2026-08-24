from sqlalchemy import func, select, tuple_

from modules.production_core.persistence import (
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.work_order_progress import (
    calculate_work_order_progress,
    order_remaining_expression,
)


PositionKey = tuple[int, str, str]


WORK_STATUS_PRIORITY = {
    "completed": 0,
    "unprocessed": 1,
    "processing": 2,
    "processing_completed": 3,
    "qc": 4,
    "rework": 5,
}


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
    return "processing_completed" if progress.ready_for_qc_quantity > 0 else "processing"


def dominant_work_status(statuses, default: str = "unprocessed") -> str:
    return max(
        statuses,
        key=lambda status: WORK_STATUS_PRIORITY.get(status, 1),
        default=default,
    )


def _stages_by_order(session, orders: list[WorkOrder]) -> dict[int, str]:
    if not orders:
        return {}
    batches_by_order: dict[int, list[WorkOrderBatch]] = {
        order.id: [] for order in orders
    }
    for batch in session.scalars(
        select(WorkOrderBatch).where(
            WorkOrderBatch.work_order_id.in_(list(batches_by_order))
        )
    ):
        batches_by_order[batch.work_order_id].append(batch)
    return {
        order.id: work_order_stage(order, batches_by_order[order.id])
        for order in orders
    }


def reserved_quantities(session, repository_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    if not repository_ids:
        return result
    for repository_id, quantity in session.execute(
        select(
            WorkOrder.repository_id,
            func.sum(order_remaining_expression()),
        )
        .where(WorkOrder.repository_id.in_(repository_ids), WorkOrder.status == "open")
        .group_by(WorkOrder.repository_id)
    ):
        result[repository_id] = quantity
    for repository_id, quantity in session.execute(
        select(WorkOrderMaterial.repository_id, func.sum(WorkOrderMaterial.quantity))
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
        .where(
            WorkOrderMaterial.repository_id.in_(repository_ids),
            WorkOrder.status == "open",
        )
        .group_by(WorkOrderMaterial.repository_id)
    ):
        result[repository_id] = result.get(repository_id, 0) + quantity
    return result


def position_statuses(
    session,
    department_id: int,
    department_code: str,
    positions: list[PositionKey],
) -> dict[PositionKey, str]:
    if not positions:
        return {}
    if department_code == "assembly":
        rows = session.execute(
            select(
                Repository.production_item_id,
                Repository.flow_node_id,
                Repository.source_flow_node_id,
                WorkOrder,
            )
            .join(
                WorkOrderMaterial,
                WorkOrderMaterial.repository_id == Repository.id,
            )
            .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
            .where(
                Repository.department_id == department_id,
                tuple_(
                    Repository.production_item_id,
                    Repository.flow_node_id,
                    Repository.source_flow_node_id,
                ).in_(positions),
                WorkOrder.status == "open",
            )
        ).all()
    else:
        rows = session.execute(
            select(
                Repository.production_item_id,
                Repository.flow_node_id,
                Repository.source_flow_node_id,
                WorkOrder,
            )
            .join(WorkOrder, WorkOrder.repository_id == Repository.id)
            .where(
                Repository.department_id == department_id,
                tuple_(
                    Repository.production_item_id,
                    Repository.flow_node_id,
                    Repository.source_flow_node_id,
                ).in_(positions),
                WorkOrder.status == "open",
            )
        ).all()

    orders = list({row.WorkOrder.id: row.WorkOrder for row in rows}.values())
    stages = _stages_by_order(session, orders)
    statuses_by_position: dict[PositionKey, list[str]] = {}
    for production_item_id, flow_node_id, source_flow_node_id, order in rows:
        position = (production_item_id, flow_node_id, source_flow_node_id)
        statuses_by_position.setdefault(position, []).append(stages[order.id])

    return {
        position: dominant_work_status(statuses_by_position.get(position, []))
        for position in positions
    }
