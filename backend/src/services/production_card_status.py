from sqlalchemy import exists, func, or_, select

from models.production import (
    ProductionMovement,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)


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


def position_status(
    session,
    department_code: str,
    production_item_id: int,
    node_id: str,
) -> str:
    if department_code == "qc":
        pending = session.scalar(
            select(func.count(WorkOrderBatch.id))
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(
                WorkOrder.production_item_id == production_item_id,
                WorkOrderBatch.flow_node_id == node_id,
                WorkOrderBatch.recorded_at.is_(None),
            )
        )
        return "unprocessed" if pending else "completed"

    statement = select(WorkOrder).where(WorkOrder.flow_node_id == node_id)
    if department_code == "assembly":
        statement = statement.where(
            or_(
                WorkOrder.production_item_id == production_item_id,
                exists(
                    select(WorkOrderMaterial.id).where(
                        WorkOrderMaterial.work_order_id == WorkOrder.id,
                        WorkOrderMaterial.production_item_id == production_item_id,
                    )
                ),
            )
        )
    else:
        statement = statement.where(WorkOrder.production_item_id == production_item_id)
    orders = [
        item for item in session.scalars(statement).all() if item.status != "cancelled"
    ]
    if any(item.status == "open" for item in orders):
        return "processing"
    latest_closed = max(
        (item.closed_at for item in orders if item.status == "closed" and item.closed_at),
        default=None,
    )
    latest_arrival = session.scalar(
        select(func.max(ProductionMovement.created_at)).where(
            ProductionMovement.production_item_id == production_item_id,
            ProductionMovement.target_flow_node_id == node_id,
        )
    )
    return "completed" if latest_closed and (
        latest_arrival is None or latest_closed >= latest_arrival
    ) else "unprocessed"


def arrival_time(
    session,
    production_item_id: int,
    node_id: str,
    department_id: int,
) -> str | None:
    value = session.scalar(
        select(func.max(ProductionMovement.created_at)).where(
            ProductionMovement.production_item_id == production_item_id,
            ProductionMovement.target_flow_node_id == node_id,
            ProductionMovement.target_department_id == department_id,
        )
    )
    return value.isoformat(timespec="minutes") if value else None
