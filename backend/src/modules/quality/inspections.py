from dataclasses import dataclass

from sqlalchemy.orm import Session

from domain.production_types import (
    QC_SUPPORTED_WORK_ORDER_TYPES,
    REWORK_TRACKED_WORK_ORDER_TYPES,
    WORK_ORDER_STATUS_OPEN,
    QcQualifiedDestination,
)
from domain.workforce import WorkerReference
from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import (
    get_department_ids_by_codes,
    get_procedure_routes,
)
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.flow_api import (
    ProductionFlowContext,
    qc_qualified_destinations,
)
from modules.production_core.operational_api import (
    node_context,
    process_qc_node,
    record_movement,
    refresh_qc_work_order_closed,
    serialize_batch,
)
from modules.production_core.qc_api import (
    load_qc_production_item,
    load_qc_work_order,
    record_qc_batch_result,
    record_qc_batch_destination,
)
from modules.quality.inspection_api import load_inspection_batch
from modules.quality.inspection_rules import validate_inspection_result
from modules.quality.routing_api import QcRoutingStrategy
from schemas.production import QcInspection


@dataclass(frozen=True)
class PreparedInspection:
    session: Session
    batch: InspectionBatchContext
    order: WorkOrderContext
    production_item: ProductionItemContext
    procedure: ProcedureContext
    flow_context: ProductionFlowContext
    flow_node: dict
    qc_department_id: int
    qc_worker: WorkerReference


@dataclass(frozen=True)
class PreparedDestination:
    session: Session
    batch: InspectionBatchContext
    order: WorkOrderContext
    production_item: ProductionItemContext
    procedure: ProcedureContext
    flow_context: ProductionFlowContext
    flow_node: dict
    qc_flow_node_id: str
    qc_department_id: int
    destination: QcQualifiedDestination
    already_decided: bool


def prepare_inspection(
    session,
    batch_id: int,
    payload: QcInspection,
    qc_worker: WorkerReference | None,
) -> PreparedInspection:
    qc_department_id, qc_worker = _validate_qc_worker(
        session,
        qc_worker,
    )
    batch, order = _load_locked_inspection(session, batch_id)
    _validate_pending_inspection(batch, order, payload)
    production_item, context, node, procedure = _load_execution_context(
        session,
        order,
    )

    return PreparedInspection(
        session=session,
        batch=batch,
        order=order,
        production_item=production_item,
        procedure=procedure,
        flow_context=context,
        flow_node=node,
        qc_department_id=qc_department_id,
        qc_worker=qc_worker,
    )


def _validate_qc_worker(
    session,
    qc_worker: WorkerReference | None,
) -> tuple[int, WorkerReference]:
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if (
        qc_department_id is None
        or qc_worker is None
        or qc_worker.department_id != qc_department_id
    ):
        raise DomainError("qc_worker_invalid", "请选择有效的 QC 工人")
    return qc_department_id, qc_worker


def _load_locked_inspection(
    session,
    batch_id: int,
) -> tuple[InspectionBatchContext, WorkOrderContext]:
    batch = load_inspection_batch(session, batch_id)
    if batch is None:
        raise DomainError("qc_batch_not_found", "送检批次不存在", status_code=404)
    order = load_qc_work_order(session, batch.work_order_id, for_update=True)
    if order is None or batch.work_order_id != order.id:
        raise DomainError("qc_batch_not_found", "送检批次所属工单不存在", status_code=404)
    batch = load_inspection_batch(session, batch_id, for_update=True)
    if batch is None:
        raise DomainError("qc_batch_not_found", "送检批次不存在", status_code=404)
    return batch, order


def _validate_pending_inspection(
    batch: InspectionBatchContext,
    order: WorkOrderContext,
    payload: QcInspection,
) -> None:
    if batch.recorded_at is not None:
        raise DomainError("qc_batch_completed", "该批次已经完成质检")
    if order.work_order_type not in QC_SUPPORTED_WORK_ORDER_TYPES:
        raise DomainError("qc_work_order_type_invalid", "当前工单不支持送 QC")
    if (
        order.work_order_type in REWORK_TRACKED_WORK_ORDER_TYPES
        and order.status != WORK_ORDER_STATUS_OPEN
    ):
        raise DomainError("work_order_closed", "生产工单已经结单")

    validate_inspection_result(
        submitted_quantity=batch.submitted_quantity,
        qualified_quantity=payload.qualified_quantity,
        rework_quantity=payload.rework_quantity,
        scrap_quantity=payload.scrap_quantity,
        lost_quantity=payload.lost_quantity,
        defect_reason=payload.defect_reason,
    )


def _load_execution_context(
    session,
    order: WorkOrderContext,
) -> tuple[ProductionItemContext, ProductionFlowContext, dict, ProcedureContext]:
    production_item = load_qc_production_item(
        session,
        order.production_item_id,
        for_update=True,
    )
    if production_item is None:
        raise DomainError("production_context_missing", "送检工单的生产资料不完整")
    context, node = node_context(session, production_item, order.flow_node_id)
    procedure_id = order.procedure_id
    procedure = (
        get_procedure_routes(session, {procedure_id}).get(procedure_id)
        if procedure_id is not None
        else None
    )
    if (
        procedure_id is None
        or procedure is None
        or procedure.workshop_id != node.get("workshop_id")
    ):
        raise DomainError("production_context_missing", "送检工单的工艺资料不完整")
    return production_item, context, node, procedure


def record_inspection_result(
    prepared: PreparedInspection,
    payload: QcInspection,
    routing: QcRoutingStrategy,
) -> dict:
    session = prepared.session
    batch = prepared.batch
    order = prepared.order
    production_item = prepared.production_item
    procedure = prepared.procedure
    context = prepared.flow_context
    node = prepared.flow_node
    qc_department_id = prepared.qc_department_id

    routing.validate_context(session, order, procedure)
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    qc_flow_node_id = qc_node["id"] if qc_node is not None else node["id"]
    if payload.rework_quantity:
        route_result = routing.route_rework(
            session,
            order=order,
            batch=batch,
            production_item=production_item,
            procedure=procedure,
            node=node,
            quantity=payload.rework_quantity,
        )
        record_movement(
            session,
            production_item=production_item,
            quantity=payload.rework_quantity,
            movement_type="qc_rework",
            source_flow_node_id=qc_flow_node_id,
            target_flow_node_id=node["id"],
            source_department_id=qc_department_id,
            target_department_id=route_result.target_department_id,
            work_order=order,
            work_order_batch=batch,
        )

    _record_loss(
        session,
        production_item,
        order,
        batch,
        qc_flow_node_id,
        payload.scrap_quantity,
        "scrap",
        qc_department_id,
    )
    _record_loss(
        session,
        production_item,
        order,
        batch,
        qc_flow_node_id,
        payload.lost_quantity,
        "lost",
        qc_department_id,
    )
    session.flush()
    record_qc_batch_result(
        batch,
        qualified_quantity=payload.qualified_quantity,
        rework_quantity=payload.rework_quantity,
        scrap_quantity=payload.scrap_quantity,
        lost_quantity=payload.lost_quantity,
        qc_worker_id=prepared.qc_worker.id,
        qc_worker_name=prepared.qc_worker.worker_name,
        defect_reason=(payload.defect_reason or "").strip() or None,
    )
    session.flush()
    refresh_qc_work_order_closed(session, order)
    session.flush()
    return serialize_batch(
        batch,
        rework_pending_quantity=payload.rework_quantity,
        track_rework=order.work_order_type in REWORK_TRACKED_WORK_ORDER_TYPES,
    )


def prepare_qualified_destination(
    session: Session,
    batch_id: int,
    destination: QcQualifiedDestination,
) -> PreparedDestination:
    batch, order = _load_locked_inspection(session, batch_id)
    if order.work_order_type not in QC_SUPPORTED_WORK_ORDER_TYPES:
        raise DomainError(
            "qc_work_order_type_invalid",
            "当前工单不支持普通 QC 去向操作",
            status_code=409,
        )
    if batch.recorded_at is None:
        raise DomainError("qc_result_required", "请先录入 QC 结果", status_code=409)
    if not batch.qualified_quantity:
        raise DomainError("qc_destination_not_required", "该批次没有待处理合格品", status_code=409)
    if batch.destination_decided_at is not None:
        if batch.qualified_destination != destination:
            raise DomainError("qc_destination_conflict", "该批次合格品去向已经确定", status_code=409)
        already_decided = True
    else:
        already_decided = False

    production_item, context, node, procedure = _load_execution_context(session, order)
    allowed = qc_qualified_destinations(context.flow, context.nodes, node["id"])
    if destination not in allowed:
        raise DomainError("qc_destination_invalid", "当前批次不支持所选合格品去向", status_code=409)
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if qc_department_id is None:
        raise DomainError("department_not_found", "QC 部门不存在")
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    return PreparedDestination(
        session=session,
        batch=batch,
        order=order,
        production_item=production_item,
        procedure=procedure,
        flow_context=context,
        flow_node=node,
        qc_flow_node_id=qc_node["id"] if qc_node is not None else node["id"],
        qc_department_id=qc_department_id,
        destination=destination,
        already_decided=already_decided,
    )


def route_qualified_destination(
    prepared: PreparedDestination,
    routing: QcRoutingStrategy,
) -> None:
    routing.validate_context(prepared.session, prepared.order, prepared.procedure)
    route_result = routing.route_qualified(
        prepared.session,
        order=prepared.order,
        batch=prepared.batch,
        production_item=prepared.production_item,
        procedure=prepared.procedure,
        context=prepared.flow_context,
        node=prepared.flow_node,
        quantity=prepared.batch.qualified_quantity or 0,
        destination=prepared.destination,
    )
    record_movement(
        prepared.session,
        production_item=prepared.production_item,
        quantity=prepared.batch.qualified_quantity or 0,
        movement_type="qc_qualified",
        source_flow_node_id=prepared.qc_flow_node_id,
        target_flow_node_id=route_result.target_flow_node_id,
        source_department_id=prepared.qc_department_id,
        target_department_id=route_result.target_department_id,
        work_order=prepared.order,
        work_order_batch=prepared.batch,
    )


def finalize_qualified_destination(
    prepared: PreparedDestination,
    actor_username: str,
) -> dict:
    prepared.session.flush()
    record_qc_batch_destination(
        prepared.batch,
        destination=prepared.destination,
        actor_username=actor_username,
    )
    prepared.session.flush()
    refresh_qc_work_order_closed(prepared.session, prepared.order)
    prepared.session.flush()
    return serialize_batch(prepared.batch)


def serialize_decided_destination(prepared: PreparedDestination) -> dict:
    return serialize_batch(prepared.batch)


def _record_loss(
    session,
    production_item,
    order,
    batch,
    flow_node_id,
    quantity,
    movement_type,
    qc_department_id,
) -> None:
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type=movement_type,
        source_flow_node_id=flow_node_id,
        target_flow_node_id=None,
        source_department_id=qc_department_id,
        work_order=order,
        work_order_batch=batch,
    )
