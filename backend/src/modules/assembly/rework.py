from __future__ import annotations

"""Assembly QC rework resubmission."""

from database import SessionLocal
from domain.identity import can_access_department
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.assembly_api import load_assembly_work_order, load_production_item
from modules.production_core.operational_api import record_movement
from modules.production_core.operational_api import serialize_batch
from modules.production_core.operational_api import rework_pending_quantities
from modules.production_core.operational_api import process_qc_node
from modules.production_core.operational_api import capture_operation_state, record_undoable_operation
from modules.production_core.operational_api import node_context, target_department_id
from modules.quality.submission_api import create_inspection_batch
from modules.quality.inspection_api import list_inspection_batches, load_inspection_batch

def resubmit_assembly_rework_batch(
    source_batch_id: int,
    quantity: int,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        source_batch = load_inspection_batch(
            session,
            source_batch_id,
            for_update=True,
        )
        if source_batch is None:
            raise DomainError("qc_batch_not_found", "返工来源批次不存在", status_code=404)
        order = load_assembly_work_order(
            session,
            source_batch.work_order_id,
            for_update=True,
        )
        if order is None or order.work_order_type != "assembly":
            raise DomainError("qc_rework_order_invalid", "返工批次所属装配工单无效")
        if order.status != "open":
            raise DomainError("work_order_closed", "装配工单已经结单")
        before = capture_operation_state(session, order)
        if source_batch.recorded_at is None or source_batch.rework_quantity is None:
            raise DomainError("qc_batch_not_completed", "QC尚未录入返工结果")
        batches = list_inspection_batches(session, order.id)
        available = rework_pending_quantities(batches).get(source_batch.id, 0)
        if available <= 0 or quantity != available:
            raise DomainError(
                "qc_rework_full_quantity_required",
                "返工送检必须一次提交该批全部待返工数量",
            )
        if not can_access_department(user_department, user_is_system, "assembly"):
            raise DomainError("department_access_denied", "只有装配部可以提交返工送检", status_code=403)

        output_item = load_production_item(session, order.production_item_id)
        if output_item is None:
            raise DomainError("production_context_missing", "装配产出不存在")
        context, assembly_node = node_context(session, output_item, order.flow_node_id)
        qc_node = process_qc_node(context.flow, context.nodes, assembly_node["id"])
        if qc_node is None:
            raise DomainError("work_order_qc_not_configured", "装配节点后未配置QC节点")
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")

        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=quantity,
            execution_flow_node_id=assembly_node["id"],
            rework_source_batch_id=source_batch.id,
        )
        record_movement(
            session,
            production_item=output_item,
            quantity=quantity,
            movement_type="assembly_output",
            source_flow_node_id=assembly_node["id"],
            target_flow_node_id=qc_node["id"],
            source_department_id=target_department_id(session, assembly_node),
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
            department_code="assembly",
            actor_username=actor_username,
        )
        return serialize_batch(batch, track_rework=True)
