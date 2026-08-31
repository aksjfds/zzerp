from sqlalchemy import select

from database import SessionLocal
from domain.identity import can_access_department
from domain.production_types import COMPLETION_QC, WorkOrderCompletionAction
from modules.errors import DomainError
from modules.inventory.finished_receipt_api import register_pending_packaging_receipt
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes, get_department_views_by_ids
from modules.organization.transaction_api import load_procedure_context
from modules.production_core.context_api import InventorySourceContext, ProductionItemContext, WorkOrderContext
from modules.production_core.operational_api import (
    capture_operation_state,
    consume_order_source,
    create_order_record,
    move_to_node,
    node_context,
    order_remaining_quantity,
    process_qc_node,
    record_movement,
    record_undoable_operation,
    refresh_qc_work_order_closed,
    rework_pending_quantities,
    serialize_batch,
    serialize_work_order,
)
from modules.production_core.ownership_api import add_repository_quantity
from modules.production_core.transaction_api import (
    load_production_item_context,
    load_work_order_context,
    record_work_order_submission,
)
from modules.quality.inspection_api import list_inspection_batches, load_inspection_batch
from modules.quality.submission_api import create_inspection_batch
from modules.standard_execution.pricing_api import attach_work_order_price
from modules.standard_execution.procedures import material_key, procedure_department_id


def create_standard_order(
    session,
    *,
    source: InventorySourceContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    quantity: int,
    worker_id: int | None,
    worker_name: str | None,
    created_by: str,
    remark: str | None,
    is_temporary: bool,
) -> WorkOrderContext:
    order = create_order_record(
        session,
        source=source,
        production_item=production_item,
        procedure=procedure,
        quantity=quantity,
        worker_id=worker_id,
        worker_name=worker_name,
        created_by=created_by,
        work_order_type="standard",
        is_temporary=is_temporary,
        remark=remark,
    )
    attach_work_order_price(
        session,
        work_order_id=order.id,
        product_id=production_item.product_id,
        product_version=production_item.product_version,
        material_key=material_key(production_item),
        flow_node_id=source.flow_node_id,
        procedure_id=procedure.id,
        procedure_name=procedure.procedure_name,
        is_temporary=is_temporary,
    )
    return order


def submit_standard_order(
    session,
    *,
    order: WorkOrderContext,
    source: InventorySourceContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    node: dict,
    quantity: int,
    completion_action: WorkOrderCompletionAction,
) -> dict:
    if order.procedure_id != procedure.id or source.flow_node_id != node["id"]:
        raise DomainError("work_order_context_invalid", "工单与当前物料或工艺不一致")
    remaining = order_remaining_quantity(order)
    if quantity != remaining or quantity > source.quantity:
        raise DomainError("submission_must_be_full", "工单必须整单填写结果或送检")
    context, _ = node_context(session, production_item, node["id"])
    department_id = procedure_department_id(session, procedure)
    batch = None
    if completion_action == COMPLETION_QC:
        qc_node = process_qc_node(context.flow, context.nodes, node["id"])
        if qc_node is None:
            raise DomainError("work_order_qc_not_configured", "当前车间节点后未配置QC节点")
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=quantity,
            execution_flow_node_id=node["id"],
        )
        target_flow_node_id = qc_node["id"]
        target_department_id = qc_department_id
    else:
        direct_target = context.normal_target(node["id"])
        if direct_target is not None and direct_target.get("type") == "finished_inbound":
            target_department_id = move_to_node(
                session,
                production_item,
                direct_target,
                quantity,
                node["id"],
                source_work_order_id=order.id,
            )
            if target_department_id is None:
                raise DomainError("finished_inbound_target_missing", "装包节点没有有效入库终点")
            register_pending_packaging_receipt(
                session,
                work_order_id=order.id,
                product_id=production_item.product_id,
                product_version=production_item.product_version,
                inbound_node_id=direct_target["id"],
                released_quantity=quantity,
            )
            target_flow_node_id = direct_target["id"]
        else:
            add_repository_quantity(
                session,
                production_item_id=production_item.id,
                flow_node_id=node["id"],
                source_flow_node_id=node["id"],
                department_id=department_id,
                quantity=quantity,
                source_work_order_id=order.id,
            )
            target_flow_node_id = node["id"]
            target_department_id = department_id
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="process",
        source_flow_node_id=node["id"],
        target_flow_node_id=target_flow_node_id,
        source_department_id=source.department_id,
        target_department_id=target_department_id,
        work_order=order,
        work_order_batch=batch,
    )
    record_work_order_submission(order, quantity)
    consume_order_source(session, order, source, quantity)
    session.flush()
    refresh_qc_work_order_closed(session, order)
    return serialize_work_order(session, order)


def resubmit_standard_rework_batch(
    source_batch_id: int,
    quantity: int,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        source_batch = load_inspection_batch(session, source_batch_id, for_update=True)
        if source_batch is None:
            raise DomainError("qc_batch_not_found", "返工来源批次不存在", status_code=404)
        order = load_work_order_context(session, source_batch.work_order_id, for_update=True)
        if order is None or order.work_order_type != "standard":
            raise DomainError("qc_rework_order_invalid", "返工批次所属工单无效")
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        before = capture_operation_state(session, order)
        if source_batch.recorded_at is None or source_batch.rework_quantity is None:
            raise DomainError("qc_batch_not_completed", "QC尚未录入返工结果")
        available = rework_pending_quantities(
            list_inspection_batches(session, order.id)
        ).get(source_batch.id, 0)
        if available <= 0 or quantity != available:
            raise DomainError("qc_rework_full_quantity_required", "返工送检必须一次提交全部待返工数量")
        production_item = load_production_item_context(session, order.production_item_id)
        if production_item is None:
            raise DomainError("production_context_missing", "生产项不存在")
        _, node = node_context(session, production_item, order.flow_node_id)
        procedure = load_procedure_context(session, order.procedure_id)
        if procedure is None:
            raise DomainError("procedure_not_found", "工单工艺不存在")
        department_id = procedure_department_id(session, procedure)
        department = next(iter(get_department_views_by_ids(session, {department_id})), None)
        if department is None or not can_access_department(
            user_department,
            user_is_system,
            department.department_code,
        ):
            raise DomainError("department_access_denied", "无权提交返工送检", status_code=403)
        qc_node = process_qc_node(
            node_context(session, production_item, node["id"])[0].flow,
            node_context(session, production_item, node["id"])[0].nodes,
            node["id"],
        )
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_node is None or qc_department_id is None:
            raise DomainError("work_order_qc_not_configured", "当前车间节点后未配置QC节点")
        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=quantity,
            execution_flow_node_id=node["id"],
            rework_source_batch_id=source_batch.id,
        )
        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="process",
            source_flow_node_id=node["id"],
            target_flow_node_id=qc_node["id"],
            source_department_id=department_id,
            target_department_id=qc_department_id,
            work_order=order,
            work_order_batch=batch,
        )
        session.flush()
        record_undoable_operation(
            session,
            order,
            before,
            operation_type="rework_submission",
            operation_label="撤回返工送检",
            department_code=department.department_code,
            actor_username=actor_username,
        )
        return serialize_batch(batch, track_rework=True)
