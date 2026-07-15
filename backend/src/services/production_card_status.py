from sqlalchemy import func, select, tuple_

from models.production import (
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)


PositionKey = tuple[int, str, str]


def reserved_quantities(session, repository_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    if not repository_ids:
        return result
    for repository_id, quantity in session.execute(
        select(
            WorkOrder.repository_id,
            func.sum(WorkOrder.quantity - WorkOrder.completed_quantity),
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
    if department_code == "qc":
        pending_positions = set(
            session.execute(
                select(
                    WorkOrder.production_item_id,
                    WorkOrderBatch.flow_node_id,
                    WorkOrder.flow_node_id,
                )
                .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
                .where(
                    tuple_(
                        WorkOrder.production_item_id,
                        WorkOrderBatch.flow_node_id,
                        WorkOrder.flow_node_id,
                    ).in_(positions),
                    WorkOrderBatch.recorded_at.is_(None),
                )
            ).all()
        )
        return {
            position: "unprocessed" if position in pending_positions else "completed"
            for position in positions
        }

    if department_code == "assembly":
        processing_positions = set(
            session.execute(
                select(
                    Repository.production_item_id,
                    Repository.flow_node_id,
                    Repository.source_flow_node_id,
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
        )
    else:
        processing_positions = set(
            session.execute(
                select(
                    Repository.production_item_id,
                    Repository.flow_node_id,
                    Repository.source_flow_node_id,
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
        )

    return {
        position: "processing" if position in processing_positions else "unprocessed"
        for position in positions
    }
