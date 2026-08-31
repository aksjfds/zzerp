"""Narrow production activity reads used by the department workbench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from domain.production_types import (
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_STANDARD,
    WORK_ORDER_STATUS_CLOSED,
    WORK_ORDER_STATUS_OPEN,
    WorkOrderStatus,
)
from modules.errors import DomainError
from modules.organization.model_api import Procedure, Workshop
from modules.production_core.persistence import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.work_order_status import (
    reserved_quantities,
    work_order_stage,
)
from modules.production_core.flow_api import (
    ProductionFlowContext,
    completed_node_display_label,
    load_production_flow,
)
from modules.production_core.work_order_presenters import (
    WorkOrderPresenterContext,
    build_work_order_presenter_context,
    item_display,
    serialize_work_order,
)
from modules.production_core.work_order_progress import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
)


StandardPositionKey = tuple[int, str, str]
AssemblyPositionKey = tuple[int, str]

__all__ = [
    "AssemblyInputAllocation",
    "PositionActivity",
    "WorkbenchPositionWorkOrders",
    "load_assembly_position_work_orders",
    "load_standard_position_work_orders",
    "load_workbench_activity",
    "reserved_quantities",
]


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


@dataclass(frozen=True, slots=True)
class WorkbenchWorkOrderProgress:
    work_order_id: int
    procedure_id: int
    procedure_name: str
    is_temporary: bool
    status: WorkOrderStatus
    work_order_quantity: int
    processing_quantity: int
    ready_for_result_quantity: int
    pending_qc_quantity: int
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int


@dataclass(frozen=True, slots=True)
class WorkbenchPositionWorkOrders:
    work_orders: tuple[dict, ...]
    progress: tuple[WorkbenchWorkOrderProgress, ...]
    total: int


def load_workbench_activity(
    session: Session,
    department_id: int,
    department_code: str,
) -> WorkbenchActivitySnapshot:
    """Load all open work-order activity without exposing persistence records."""
    condition = (
        (WorkOrder.work_order_type == WORK_ORDER_STANDARD)
        & (Workshop.department_id == department_id)
    )
    if department_code == "assembly":
        condition = or_(condition, WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY)
    rows = session.execute(
        select(WorkOrder, ProductionItem.customer_order_item_id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
        .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
        .where(WorkOrder.status == WORK_ORDER_STATUS_OPEN, condition)
    ).all()
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


def load_standard_position_work_orders(
    session: Session,
    *,
    department_id: int,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    page: int,
    page_size: int,
    procedure_id: int | None = None,
    is_temporary: bool | None = None,
) -> WorkbenchPositionWorkOrders:
    source_order_ids = {
        source_order_id
        for source_order_id in session.scalars(
            select(Repository.source_work_order_id).where(
                Repository.department_id == department_id,
                Repository.production_item_id == production_item_id,
                Repository.flow_node_id == flow_node_id,
                Repository.source_flow_node_id == source_flow_node_id,
                Repository.source_work_order_id.is_not(None),
            )
        )
        if source_order_id is not None
    }
    position_condition = WorkOrder.source_flow_node_id == source_flow_node_id
    if source_order_ids:
        position_condition = or_(
            position_condition,
            WorkOrder.id.in_(source_order_ids),
        )
    orders = list(session.scalars(
        _ordered_work_orders()
        .join(Procedure, Procedure.id == WorkOrder.procedure_id)
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .where(
            WorkOrder.work_order_type == WORK_ORDER_STANDARD,
            WorkOrder.production_item_id == production_item_id,
            WorkOrder.flow_node_id == flow_node_id,
            Workshop.department_id == department_id,
            position_condition,
        )
    ))
    return _position_work_orders(
        session,
        orders,
        page,
        page_size,
        procedure_id=procedure_id,
        is_temporary=is_temporary,
    )


def load_assembly_position_work_orders(
    session: Session,
    *,
    customer_order_item_id: int,
    flow_node_id: str,
    page: int,
    page_size: int,
    procedure_id: int | None = None,
    is_temporary: bool | None = None,
) -> WorkbenchPositionWorkOrders:
    orders = list(session.scalars(
        _ordered_work_orders()
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
            ProductionItem.customer_order_item_id == customer_order_item_id,
            WorkOrder.flow_node_id == flow_node_id,
        )
    ))
    return _position_work_orders(
        session,
        orders,
        page,
        page_size,
        procedure_id=procedure_id,
        is_temporary=is_temporary,
    )


def _ordered_work_orders():
    return select(WorkOrder).order_by(
        case(
            (WorkOrder.status == WORK_ORDER_STATUS_OPEN, 0),
            (WorkOrder.status == WORK_ORDER_STATUS_CLOSED, 1),
            else_=2,
        ),
        WorkOrder.id.desc(),
    )


def _position_work_orders(
    session: Session,
    orders: list[WorkOrder],
    page: int,
    page_size: int,
    *,
    procedure_id: int | None,
    is_temporary: bool | None,
) -> WorkbenchPositionWorkOrders:
    if not orders:
        return WorkbenchPositionWorkOrders((), (), 0)
    context = build_work_order_presenter_context(session, orders)
    progress = tuple(
        _workbench_order_progress(session, order, context)
        for order in orders
    )
    filtered = [
        order
        for order in orders
        if (procedure_id is None or order.procedure_id == procedure_id)
        and (is_temporary is None or order.is_temporary == is_temporary)
    ]
    selected = filtered[(page - 1) * page_size:page * page_size]
    inputs_by_order = _workbench_input_materials(session, selected, context)
    return WorkbenchPositionWorkOrders(
        work_orders=tuple(
            {
                **serialize_work_order(session, order, context),
                "input_materials": inputs_by_order.get(order.id, []),
            }
            for order in selected
        ),
        progress=progress,
        total=len(filtered),
    )


def _workbench_input_materials(
    session: Session,
    orders: list[WorkOrder],
    context: WorkOrderPresenterContext,
) -> dict[int, list[dict]]:
    order_ids = {order.id for order in orders}
    if not order_ids:
        return {}
    materials = list(session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id.in_(order_ids))
        .order_by(WorkOrderMaterial.work_order_id, WorkOrderMaterial.id)
    ))
    source_order_ids = {
        material.source_work_order_id
        for material in materials
        if material.source_work_order_id is not None
    }
    source_orders = {
        order.id: order
        for order in session.scalars(
            select(WorkOrder).where(WorkOrder.id.in_(source_order_ids))
        )
    } if source_order_ids else {}
    result: dict[int, list[dict]] = {}
    for material in materials:
        production_item = context.display.production_items.get(
            material.production_item_id,
        )
        if production_item is None:
            raise DomainError(
                "assembly_material_missing",
                "装配工单投入物料不存在",
                status_code=409,
            )
        flow_context = load_production_flow(
            session,
            production_item,
            flow_cache=context.display.flow_cache,
            order_items=context.display.order_items,
            bom_items=context.display.bom_items,
        )
        item_code, item_name = item_display(
            session,
            production_item,
            context.display,
        )
        source_order = source_orders.get(material.source_work_order_id)
        result.setdefault(material.work_order_id, []).append({
            "production_item_id": material.production_item_id,
            "item_code": item_code,
            "item_name": item_name,
            "quantity": material.quantity,
            "source_completion": _source_completion_label(
                flow_context,
                production_item,
                material.source_previous_flow_node_id,
            ),
            "source_work_order_no": (
                source_order.work_order_no if source_order is not None else None
            ),
        })
    return result


def _source_completion_label(
    flow_context: ProductionFlowContext,
    production_item: ProductionItem,
    completed_flow_node_id: str,
) -> str:
    if completed_flow_node_id == production_item.origin_flow_node_id:
        origin = flow_context.nodes.get(production_item.origin_flow_node_id)
        if origin is not None and origin.get("type") == "part":
            return "初始物料"
    return completed_node_display_label(
        flow_context.flow,
        flow_context.nodes,
        production_item.origin_flow_node_id,
        completed_flow_node_id,
    )


def _workbench_order_progress(
    session: Session,
    order: WorkOrder,
    context: WorkOrderPresenterContext,
) -> WorkbenchWorkOrderProgress:
    if order.procedure_id is None:
        raise DomainError(
            "work_order_procedure_missing",
            "生产工单缺少工艺",
            status_code=409,
        )
    procedure = context.procedures.get(order.procedure_id)
    batches = context.batches.get(order.id, [])
    progress = calculate_work_order_progress(order, batches)
    work_order_quantity = order.quantity
    processing_quantity = progress.processing_quantity
    ready_for_result_quantity = progress.ready_for_qc_quantity
    qualified_quantity = progress.qualified_quantity
    if order.work_order_type == WORK_ORDER_ASSEMBLY:
        production_item = context.display.production_items[order.production_item_id]
        flow_context = load_production_flow(
            session,
            production_item,
            flow_cache=context.display.flow_cache,
            order_items=context.display.order_items,
            bom_items=context.display.bom_items,
        )
        output_unit_quantity = max(
            int(flow_context.nodes.get(order.flow_node_id, {}).get("output_pcs") or 1),
            1,
        )
        output = calculate_assembly_output_progress(
            order,
            batches,
            output_unit_quantity,
        )
        work_order_quantity = order.quantity * output_unit_quantity
        processing_quantity = output.processing_quantity
        ready_for_result_quantity = output.ready_for_qc_quantity
        qualified_quantity = output.qualified_quantity
    return WorkbenchWorkOrderProgress(
        work_order_id=order.id,
        procedure_id=order.procedure_id,
        procedure_name=(
            procedure.procedure_name if procedure is not None else order.work_order_name
        ),
        is_temporary=order.is_temporary,
        status=order.status,
        work_order_quantity=work_order_quantity,
        processing_quantity=processing_quantity,
        ready_for_result_quantity=ready_for_result_quantity,
        pending_qc_quantity=progress.pending_qc_quantity,
        qualified_quantity=qualified_quantity,
        rework_quantity=progress.rework_quantity,
        scrap_quantity=progress.scrap_quantity,
        lost_quantity=progress.lost_quantity,
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
    "WorkbenchPositionWorkOrders",
    "WorkbenchWorkOrderProgress",
    "load_assembly_position_work_orders",
    "load_standard_position_work_orders",
    "load_workbench_activity",
]
