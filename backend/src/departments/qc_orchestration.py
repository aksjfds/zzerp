"""Application orchestration for QC inspection and execution routing."""

from sqlalchemy import select

from database import SessionLocal
from domain.identity import can_access_department
from domain.production_types import (
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_STANDARD,
)
from domain.warehouse import (
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_SOURCE_QC_INVENTORY,
    WarehouseOperationContext,
)
import modules.assembly.qc_api as assembly_qc_routing
from modules.errors import DomainError
from modules.inventory.warehouse_api import WarehouseInboundRequest, receive_c01_stock
from modules.inventory.warehouse_api import (
    next_qc_inventory_operation_group,
    reverse_latest_qc_inventory_operation,
)
from modules.inventory.finished_receipt_api import cancel_pending_qc_receipt
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.qc_inventory_api import (
    project_qc_inventory_material,
    record_qc_inventory_movement,
)
from modules.production_core.qc_api import undo_qc_batch_result
from modules.production_core.model_api import ProductionOperationUndo, WorkOrderBatch
from modules.production_core.operational_api import (
    capture_operation_state,
    record_undoable_operation,
    undo_production_operation_in_session,
)
from modules.quality.command_api import (
    PreparedDestination,
    finalize_qualified_destination,
    prepare_inspection,
    prepare_qualified_destination,
    record_inspection_result,
    route_qualified_destination,
    serialize_decided_destination,
)
from modules.quality.routing_api import QcRoutingStrategy
import modules.standard_execution.qc_api as standard_qc_routing
from modules.workforce.reference_api import get_worker_reference
from schemas.production import QcDestinationInput, QcInspection


QC_ROUTING_STRATEGIES: dict[str, QcRoutingStrategy] = {
    WORK_ORDER_STANDARD: standard_qc_routing,
    WORK_ORDER_ASSEMBLY: assembly_qc_routing,
}


def inspect_qc_batch(
    batch_id: int,
    payload: QcInspection,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError("qc_access_denied", "只有 QC 可以录入质检结果", status_code=403)
    with SessionLocal.begin() as session:
        prepared = prepare_inspection(
            session,
            batch_id,
            payload,
            get_worker_reference(session, payload.qc_worker_id),
        )
        try:
            routing = QC_ROUTING_STRATEGIES[prepared.order.work_order_type]
        except KeyError as exc:
            raise DomainError(
                "qc_work_order_type_invalid",
                "当前工单不支持送 QC",
            ) from exc
        return record_inspection_result(prepared, payload, routing)


def undo_qc_inspection(
    batch_id: int,
    actor_department: str | None,
    actor_is_system: bool,
) -> None:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError("qc_access_denied", "只有 QC 可以撤回质检结果", status_code=403)
    with SessionLocal.begin() as session:
        undo_qc_batch_result(session, batch_id)


def decide_qc_destination(
    batch_id: int,
    payload: QcDestinationInput,
    actor_username: str,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError("qc_access_denied", "只有 QC 可以决定合格品去向", status_code=403)
    with SessionLocal.begin() as session:
        prepared = prepare_qualified_destination(session, batch_id, payload.destination)
        if prepared.already_decided:
            return serialize_decided_destination(prepared)
        before = capture_operation_state(session, prepared.order)
        try:
            routing = QC_ROUTING_STRATEGIES[prepared.order.work_order_type]
        except KeyError as exc:
            raise DomainError(
                "qc_work_order_type_invalid",
                "当前工单不支持送 QC",
            ) from exc

        if payload.destination == "inventory":
            _store_qualified_material(prepared, actor_username)
        else:
            route_qualified_destination(prepared, routing)
        result = finalize_qualified_destination(prepared, actor_username)
        record_undoable_operation(
            session,
            prepared.order,
            before,
            operation_type="qc_destination",
            operation_label="撤回质检去向",
            department_code="qc",
            actor_username=actor_username,
            work_order_batch_id=prepared.batch.id,
        )
        return result


def undo_qc_destination(
    batch_id: int,
    actor_username: str,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError("qc_access_denied", "只有 QC 可以撤回合格品去向", status_code=403)
    with SessionLocal.begin() as session:
        batch = session.get(WorkOrderBatch, batch_id, with_for_update=True)
        if batch is None or batch.qualified_destination is None:
            raise DomainError("qc_destination_not_found", "该批次尚未决定合格品去向", status_code=404)
        operation = session.scalar(
            select(ProductionOperationUndo)
            .where(
                ProductionOperationUndo.work_order_batch_id == batch.id,
                ProductionOperationUndo.operation_type == "qc_destination",
                ProductionOperationUndo.status == "applied",
            )
            .order_by(ProductionOperationUndo.id.desc())
            .with_for_update()
        )
        if operation is None:
            raise DomainError("qc_destination_not_reversible", "该质检去向没有可撤回记录", status_code=409)
        cancel_pending_qc_receipt(
            session,
            work_order_batch_id=batch.id,
            actor_username=actor_username,
        )
        if batch.qualified_destination == "inventory":
            result = reverse_latest_qc_inventory_operation(
                session,
                work_order_batch_id=batch.id,
                actor_username=actor_username,
            )
            if result.status != WAREHOUSE_OPERATION_SUCCEEDED:
                raise DomainError(
                    "qc_inventory_reversal_failed",
                    result.error_message or "仓库入库冲销失败",
                    status_code=409,
                )
        return undo_production_operation_in_session(
            session,
            operation.id,
            actor_department,
            actor_is_system,
            actor_username,
        )


def _store_qualified_material(
    prepared: PreparedDestination,
    actor_username: str,
) -> None:
    warehouse_department_id = get_department_ids_by_codes(
        prepared.session,
        {"warehouse"},
    ).get("warehouse")
    if warehouse_department_id is None:
        raise DomainError("department_not_found", "仓库部门不存在")
    material = project_qc_inventory_material(
        prepared.session,
        prepared.production_item,
        prepared.flow_context,
        prepared.order,
        prepared.flow_node["id"],
    )
    quantity = prepared.batch.qualified_quantity or 0
    result = receive_c01_stock(
        prepared.session,
        WarehouseInboundRequest(
            operation_group_no=next_qc_inventory_operation_group(
                prepared.session,
                work_order_batch_id=prepared.batch.id,
            ),
            context=WarehouseOperationContext(
                source_type=WAREHOUSE_SOURCE_QC_INVENTORY,
                work_order_id=prepared.order.id,
                work_order_batch_id=prepared.batch.id,
                production_item_id=prepared.production_item.id,
            ),
            item_code=material.item_code,
            item_name=material.item_name,
            product_version=material.product_version,
            item_type=material.item_type,
            completion_status=material.completion_status,
            processing_state_id=material.processing_state_id,
            quantity=quantity,
            actor_username=actor_username,
        ),
    )
    if result.status != WAREHOUSE_OPERATION_SUCCEEDED:
        raise DomainError(
            "warehouse_inbound_failed",
            result.error_message or "仓库入库未成功，请核对后重试",
            status_code=409,
        )
    record_qc_inventory_movement(
        prepared.session,
        production_item=prepared.production_item,
        work_order=prepared.order,
        batch=prepared.batch,
        quantity=quantity,
        qc_flow_node_id=prepared.qc_flow_node_id,
        qc_department_id=prepared.qc_department_id,
        warehouse_department_id=warehouse_department_id,
    )


__all__ = [
    "decide_qc_destination",
    "inspect_qc_batch",
    "undo_qc_destination",
    "undo_qc_inspection",
]
