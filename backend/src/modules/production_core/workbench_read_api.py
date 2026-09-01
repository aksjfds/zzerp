"""Narrow production activity reads used by the department workbench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from domain.production_types import (
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_STANDARD,
    WORK_ORDER_STATUS_OPEN,
)
from modules.organization.model_api import Procedure, Workshop
from modules.production_core.persistence import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.work_order_status import (
    reserved_quantities,
    work_order_stage,
)


StandardPositionKey = tuple[int, str, str]
AssemblyPositionKey = tuple[int, str]

@dataclass(frozen=True, slots=True)
class PositionActivity:
    open_work_order_count: int = 0
    processing_work_order_count: int = 0
    ready_for_result_work_order_count: int = 0
    pending_qc_work_order_count: int = 0
    rework_work_order_count: int = 0
    last_activity_at: datetime | None = None
    production_item_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class AssemblyInputAllocation:
    customer_order_item_id: int
    flow_node_id: str
    production_item_id: int
    quantity: int
    source_flow_node_id: str
    source_previous_flow_node_id: str
    source_work_order_id: int | None


@dataclass(frozen=True, slots=True)
class WorkbenchActivitySnapshot:
    standard: dict[StandardPositionKey, PositionActivity]
    assembly: dict[AssemblyPositionKey, PositionActivity]
    assembly_allocations: tuple[AssemblyInputAllocation, ...]


def load_workbench_activity(
    session: Session,
    department_id: int,
    department_code: str,
    *,
    customer_order_item_id: int | None = None,
    production_item_id: int | None = None,
    flow_node_id: str | None = None,
) -> WorkbenchActivitySnapshot:
    """Load scoped open work-order activity without exposing persistence records."""
    condition = (
        (WorkOrder.work_order_type == WORK_ORDER_STANDARD)
        & (Workshop.department_id == department_id)
    )
    if department_code == "assembly":
        condition = or_(condition, WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY)
    statement = (
        select(WorkOrder, ProductionItem.customer_order_item_id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
        .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
        .where(WorkOrder.status == WORK_ORDER_STATUS_OPEN, condition)
    )
    if customer_order_item_id is not None:
        statement = statement.where(
            ProductionItem.customer_order_item_id == customer_order_item_id
        )
    if production_item_id is not None:
        statement = statement.where(WorkOrder.production_item_id == production_item_id)
    if flow_node_id is not None:
        statement = statement.where(WorkOrder.flow_node_id == flow_node_id)
    rows = session.execute(statement).all()
    orders = [row.WorkOrder for row in rows]
    batches_by_order = _batches_by_order(session, orders)

    standard_stages: dict[
        StandardPositionKey,
        list[tuple[str, datetime, int]],
    ] = {}
    assembly_stages: dict[
        AssemblyPositionKey,
        list[tuple[str, datetime, int]],
    ] = {}
    for row in rows:
        order = row.WorkOrder
        activity_at = _last_activity_at(order, batches_by_order.get(order.id, ()))
        stage = work_order_stage(order, list(batches_by_order.get(order.id, ())))
        if order.work_order_type == WORK_ORDER_ASSEMBLY:
            key = (row.customer_order_item_id, order.flow_node_id)
            assembly_stages.setdefault(key, []).append(
                (stage, activity_at, order.production_item_id)
            )
        elif order.source_flow_node_id is not None:
            key = (
                order.production_item_id,
                order.flow_node_id,
                order.source_flow_node_id,
            )
            standard_stages.setdefault(key, []).append(
                (stage, activity_at, order.production_item_id)
            )

    return WorkbenchActivitySnapshot(
        standard={key: _summarize(stages) for key, stages in standard_stages.items()},
        assembly={key: _summarize(stages) for key, stages in assembly_stages.items()},
        assembly_allocations=_assembly_allocations(session, orders),
    )


def _batches_by_order(
    session: Session,
    orders: list[WorkOrder],
) -> dict[int, tuple[WorkOrderBatch, ...]]:
    result: dict[int, list[WorkOrderBatch]] = {}
    order_ids = [order.id for order in orders]
    if order_ids:
        for batch in session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.work_order_id.in_(order_ids))
        ):
            result.setdefault(batch.work_order_id, []).append(batch)
    return {order_id: tuple(batches) for order_id, batches in result.items()}


def _last_activity_at(
    order: WorkOrder,
    batches: tuple[WorkOrderBatch, ...],
) -> datetime:
    timestamps = [order.created_at]
    for batch in batches:
        if batch.recorded_at is not None:
            timestamps.append(batch.recorded_at)
        if batch.destination_decided_at is not None:
            timestamps.append(batch.destination_decided_at)
    return max(timestamps)


def _summarize(stages: list[tuple[str, datetime, int]]) -> PositionActivity:
    return PositionActivity(
        open_work_order_count=len(stages),
        processing_work_order_count=sum(
            stage == "processing" for stage, _, _ in stages
        ),
        ready_for_result_work_order_count=sum(
            stage == "processing_completed" for stage, _, _ in stages
        ),
        pending_qc_work_order_count=sum(stage == "qc" for stage, _, _ in stages),
        rework_work_order_count=sum(stage == "rework" for stage, _, _ in stages),
        last_activity_at=max(
            (timestamp for _, timestamp, _ in stages),
            default=None,
        ),
        production_item_ids=tuple(sorted({item_id for _, _, item_id in stages})),
    )


def _assembly_allocations(
    session: Session,
    orders: list[WorkOrder],
) -> tuple[AssemblyInputAllocation, ...]:
    assembly_orders = [order for order in orders if order.work_order_type == "assembly"]
    if not assembly_orders:
        return ()
    order_context = {
        order.id: (order.flow_node_id, order.production_item_id)
        for order in assembly_orders
    }
    output_items = {
        item.id: item
        for item in session.scalars(
            select(ProductionItem).where(
                ProductionItem.id.in_(
                    {production_item_id for _, production_item_id in order_context.values()}
                )
            )
        )
    }
    allocations: list[AssemblyInputAllocation] = []
    for material in session.scalars(
        select(WorkOrderMaterial).where(
            WorkOrderMaterial.work_order_id.in_(list(order_context))
        )
    ):
        flow_node_id, output_item_id = order_context[material.work_order_id]
        output_item = output_items.get(output_item_id)
        if output_item is None:
            continue
        allocations.append(AssemblyInputAllocation(
            customer_order_item_id=output_item.customer_order_item_id,
            flow_node_id=flow_node_id,
            production_item_id=material.production_item_id,
            quantity=material.quantity,
            source_flow_node_id=material.source_flow_node_id,
            source_previous_flow_node_id=material.source_previous_flow_node_id,
            source_work_order_id=material.source_work_order_id,
        ))
    return tuple(allocations)


__all__ = [
    "AssemblyInputAllocation",
    "AssemblyPositionKey",
    "PositionActivity",
    "StandardPositionKey",
    "WorkbenchActivitySnapshot",
    "load_workbench_activity",
    "reserved_quantities",
]
