"""Transaction-aware QC commands exclusive to supplier-processing orders."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from domain.production_types import (
    QC_DESTINATION_RELEASE,
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_SUPPLIER_PROCESSING,
)
from domain.workforce import WorkerReference
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.flow_api import (
    normal_target,
    process_qc_node,
    qc_release_target,
)
from modules.production_core.operational_api import (
    calculate_supplier_processing_qc_progress,
    node_context,
    record_movement,
    serialize_batch,
    validate_supplier_processing_work_order_progress,
)
from modules.production_core.qc_api import (
    create_qc_batch,
    list_qc_batches,
    load_qc_batch,
    load_qc_production_item,
    load_qc_work_order,
    record_qc_batch_result,
    record_qc_batch_destination,
    refresh_supplier_processing_release_progress,
)
from modules.quality.inspection_rules import validate_inspection_result


@dataclass(frozen=True, slots=True)
class PreparedSupplierProcessingRelease:
    session: Session
    batch: InspectionBatchContext
    order: WorkOrderContext
    production_item: ProductionItemContext
    batches: tuple[InspectionBatchContext, ...]
    qc_flow_node_id: str
    target_node: dict
    qc_department_id: int


def record_supplier_processing_inspection(
    session: Session,
    *,
    work_order_id: int,
    qualified_quantity: int,
    rework_quantity: int,
    scrap_quantity: int,
    lost_quantity: int,
    defect_reason: str | None,
    qc_worker: WorkerReference | None,
) -> dict:
    qc_worker = _validate_qc_worker(session, qc_worker)
    quantities = (
        qualified_quantity,
        rework_quantity,
        scrap_quantity,
        lost_quantity,
    )
    if any(quantity < 0 for quantity in quantities):
        raise DomainError(
            "supplier_processing_inspection_quantity_invalid",
            "质检结果数量不能小于 0",
        )
    order = load_qc_work_order(session, work_order_id, for_update=True)
    if order is None or order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError(
            "supplier_processing_work_order_not_found",
            "委外加工工单不存在",
            status_code=404,
        )
    if order.status != WORK_ORDER_STATUS_OPEN:
        raise DomainError(
            "supplier_processing_work_order_closed",
            "委外加工工单已经结单",
            status_code=409,
        )
    submitted_quantity = sum(quantities)
    if submitted_quantity <= 0:
        raise DomainError(
            "supplier_processing_inspection_quantity_required",
            "本次质检结果数量必须大于 0",
        )
    validate_inspection_result(
        submitted_quantity=submitted_quantity,
        qualified_quantity=qualified_quantity,
        rework_quantity=rework_quantity,
        scrap_quantity=scrap_quantity,
        lost_quantity=lost_quantity,
        defect_reason=defect_reason,
    )
    existing_batches = list_qc_batches(session, order.id)
    progress = calculate_supplier_processing_qc_progress(
        order,
        existing_batches,
    )
    validate_supplier_processing_work_order_progress(order, progress)
    if progress.qualified_quantity + qualified_quantity > order.quantity:
        raise DomainError(
            "supplier_processing_qualified_quantity_exceeded",
            "本次合格数量超过工单剩余待合格数量",
            status_code=409,
        )
    batch = create_qc_batch(
        session,
        work_order_id=order.id,
        submitted_quantity=submitted_quantity,
        source_flow_node_id=order.flow_node_id,
        rework_source_batch_id=None,
    )
    record_qc_batch_result(
        batch,
        qualified_quantity=qualified_quantity,
        rework_quantity=rework_quantity,
        scrap_quantity=scrap_quantity,
        lost_quantity=lost_quantity,
        qc_worker_id=qc_worker.id,
        qc_worker_name=qc_worker.worker_name,
        defect_reason=_normalize_defect_reason(defect_reason),
    )
    session.flush()
    return serialize_batch(batch, track_rework=False)


def prepare_supplier_processing_release(
    session: Session,
    batch_id: int,
) -> PreparedSupplierProcessingRelease:
    batch, order = _load_locked_supplier_processing_batch(session, batch_id)
    _validate_supplier_processing_release_batch(batch, order)
    batches = tuple(list_qc_batches(session, order.id))
    progress = calculate_supplier_processing_qc_progress(order, batches)
    validate_supplier_processing_work_order_progress(order, progress)
    production_item, qc_flow_node_id, target_node = _supplier_release_route(
        session,
        order,
    )
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if qc_department_id is None:
        raise DomainError("department_not_found", "QC 部门不存在", status_code=409)
    return PreparedSupplierProcessingRelease(
        session=session,
        batch=batch,
        order=order,
        production_item=production_item,
        batches=batches,
        qc_flow_node_id=qc_flow_node_id,
        target_node=target_node,
        qc_department_id=qc_department_id,
    )


def _load_locked_supplier_processing_batch(
    session: Session,
    batch_id: int,
) -> tuple[InspectionBatchContext, WorkOrderContext]:
    batch = load_qc_batch(session, batch_id)
    if batch is None:
        raise DomainError(
            "supplier_processing_qc_batch_not_found",
            "委外加工质检批次不存在",
            status_code=404,
        )
    order = load_qc_work_order(session, batch.work_order_id, for_update=True)
    if order is None or order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError(
            "supplier_processing_qc_batch_not_found",
            "委外加工质检批次不存在",
            status_code=404,
        )
    batch = load_qc_batch(session, batch_id, for_update=True)
    if batch is None or batch.work_order_id != order.id:
        raise DomainError(
            "supplier_processing_qc_batch_not_found",
            "委外加工质检批次不存在",
            status_code=404,
        )
    if order.status != WORK_ORDER_STATUS_OPEN:
        raise DomainError(
            "supplier_processing_work_order_closed",
            "委外加工工单已经结单",
            status_code=409,
        )
    return batch, order


def _validate_supplier_processing_release_batch(
    batch: InspectionBatchContext,
    order: WorkOrderContext,
) -> None:
    if batch.recorded_at is None:
        raise DomainError(
            "supplier_processing_qc_result_required",
            "请先录入委外加工质检结果",
            status_code=409,
        )
    if not batch.qualified_quantity:
        raise DomainError(
            "supplier_processing_release_not_required",
            "该批次没有待放行合格品",
            status_code=409,
        )
    if batch.destination_decided_at is not None:
        raise DomainError(
            "supplier_processing_destination_decided",
            "该批次合格品已经确认去向",
            status_code=409,
        )
    if (
        batch.qualified_destination is not None
        or batch.rework_source_batch_id is not None
        or batch.source_flow_node_id != order.flow_node_id
    ):
        raise DomainError(
            "supplier_processing_qc_history_invalid",
            "委外加工质检批次上下文不符合放行规则",
            status_code=409,
        )


def _supplier_release_route(
    session: Session,
    order: WorkOrderContext,
) -> tuple[ProductionItemContext, str, dict]:
    production_item = load_qc_production_item(
        session,
        order.production_item_id,
        for_update=True,
    )
    if production_item is None:
        raise DomainError(
            "supplier_processing_material_missing",
            "委外加工工单缺少对应生产物料",
            status_code=409,
        )
    context, supplier_node = node_context(
        session,
        production_item,
        order.flow_node_id,
    )
    if supplier_node.get("type") != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError(
            "supplier_processing_flow_invalid",
            "委外加工工单绑定的流程节点无效",
            status_code=409,
        )
    source_node_id = order.source_flow_node_id
    source_node = context.nodes.get(source_node_id or "")
    source_target = (
        normal_target(context.flow, context.nodes, source_node_id)
        if source_node_id is not None
        else None
    )
    if (
        source_node_id != production_item.origin_flow_node_id
        or source_node is None
        or source_node.get("type") != "part"
        or (source_target or {}).get("id") != supplier_node["id"]
    ):
        raise DomainError(
            "supplier_processing_flow_invalid",
            "委外加工工单来源节点与绑定产品版本不一致",
            status_code=409,
        )
    qc_node = process_qc_node(context.flow, context.nodes, supplier_node["id"])
    target_node = qc_release_target(
        context.flow,
        context.nodes,
        supplier_node["id"],
    )
    if (
        qc_node is None
        or target_node is None
        or target_node.get("type") not in {
            "process",
            "assembly",
            "finished_inbound",
        }
    ):
        raise DomainError(
            "supplier_processing_release_target_missing",
            "委外加工 QC 没有可放行的后续流程节点",
            status_code=409,
        )
    return production_item, qc_node["id"], target_node


def finalize_supplier_processing_release(
    prepared: PreparedSupplierProcessingRelease,
    *,
    target_department_id: int,
    actor_username: str,
) -> dict:
    quantity = prepared.batch.qualified_quantity or 0
    if quantity <= 0:
        raise DomainError(
            "supplier_processing_release_not_required",
            "该批次没有待放行合格品",
            status_code=409,
        )
    record_movement(
        prepared.session,
        production_item=prepared.production_item,
        quantity=quantity,
        movement_type="qc_qualified",
        source_flow_node_id=prepared.qc_flow_node_id,
        target_flow_node_id=prepared.target_node["id"],
        source_department_id=prepared.qc_department_id,
        target_department_id=target_department_id,
        work_order=prepared.order,
        work_order_batch=prepared.batch,
    )
    record_qc_batch_destination(
        prepared.batch,
        destination=QC_DESTINATION_RELEASE,
        actor_username=actor_username,
    )
    prepared.session.flush()
    refresh_supplier_processing_release_progress(
        prepared.order,
        prepared.batches,
    )
    prepared.session.flush()
    return serialize_batch(prepared.batch, track_rework=False)


def _validate_qc_worker(
    session: Session,
    qc_worker: WorkerReference | None,
) -> WorkerReference:
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if (
        qc_department_id is None
        or qc_worker is None
        or qc_worker.department_id != qc_department_id
    ):
        raise DomainError("qc_worker_invalid", "请选择有效的 QC 工人")
    return qc_worker


def _normalize_defect_reason(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if len(normalized) > 1000:
        raise DomainError(
            "defect_reason_too_long",
            "不良原因内容超过允许长度",
            status_code=422,
        )
    return normalized or None


__all__ = [
    "PreparedSupplierProcessingRelease",
    "finalize_supplier_processing_release",
    "prepare_supplier_processing_release",
    "record_supplier_processing_inspection",
]
