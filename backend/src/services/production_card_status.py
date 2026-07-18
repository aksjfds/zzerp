from sqlalchemy import func, select, tuple_

from models.production import (
    ProcedureStageStock,
    Repository,
    WorkOrder,
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


def reserved_stage_quantities(session, stage_stock_ids: list[int]) -> dict[int, int]:
    if not stage_stock_ids:
        return {}
    return {
        stock_id: quantity
        for stock_id, quantity in session.execute(
            select(
                WorkOrder.procedure_stage_stock_id,
                func.sum(WorkOrder.quantity - WorkOrder.completed_quantity),
            )
            .where(
                WorkOrder.procedure_stage_stock_id.in_(stage_stock_ids),
                WorkOrder.status == "open",
            )
            .group_by(WorkOrder.procedure_stage_stock_id)
        )
    }


def stage_stock_statuses(
    session,
    stage_stock_ids: list[int],
) -> dict[int, str]:
    if not stage_stock_ids:
        return {}
    processing_ids = set(
        session.scalars(
            select(ProcedureStageStock.id)
            .join(
                WorkOrder,
                WorkOrder.procedure_stage_stock_id == ProcedureStageStock.id,
            )
            .where(
                ProcedureStageStock.id.in_(stage_stock_ids),
                WorkOrder.status == "open",
            )
        )
    )
    return {
        stock_id: "processing" if stock_id in processing_ids else "unprocessed"
        for stock_id in stage_stock_ids
    }


def position_statuses(
    session,
    department_id: int,
    department_code: str,
    positions: list[PositionKey],
) -> dict[PositionKey, str]:
    if not positions:
        return {}
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
