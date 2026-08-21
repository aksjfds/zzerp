from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now, utc_now
from modules.assembly.api import (
    resubmit_assembly_rework_batch,
    restore_cancelled_assembly_materials,
    submit_assembly_work_order,
)
from modules.errors import DomainError
from modules.organization.model_api import Department, Procedure
from modules.organization.transaction_api import resolve_workshop_procedure
from modules.production_core.flow import process_qc_node
from modules.production_core.operation_undo import capture_operation_state, record_undoable_operation
from modules.production_core.persistence import WorkOrder
from modules.production_core.work_order_commands import (
    cancel_open_order,
    load_order_source,
    load_source,
    validate_worker,
)
from modules.production_core.work_order_presenters import serialize_work_order
from modules.production_core.work_order_support import ensure_production_plan_active, mark_order_planned, node_context
from modules.purchasing.api import create_purchase_order, submit_purchase_order
from modules.quality.model_api import WorkOrderBatch
from modules.standard_execution.api import (
    create_standard_order,
    procedure_department_id,
    resubmit_standard_rework_batch,
    submit_standard_order,
)


def create_work_order(
    repository_id: int,
    procedure_id: int | None,
    procedure_name: str | None,
    quantity: int,
    worker_id: int | None,
    remark: str | None,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        source, production_item = load_source(session, repository_id)
        ensure_production_plan_active(session, production_item)
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该部门物料", status_code=403)
        _, node = node_context(session, production_item, source.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有单路车间节点可以使用普通开单")
        workshop_id = node.get("workshop_id")
        if not isinstance(workshop_id, int):
            raise DomainError("workshop_not_found", "当前流程节点未配置车间")

        procedure = resolve_workshop_procedure(
            session,
            workshop_id=workshop_id,
            procedure_id=procedure_id,
            procedure_name=procedure_name,
            input_mode="single",
            procedure_type=(
                "purchase_receipt"
                if department.department_code == "purchasing"
                else "standard"
            ),
        )
        if source.department_id != procedure_department_id(session, procedure):
            raise DomainError("work_order_source_department_invalid", "工单来源不属于当前车间部门")
        validate_worker(session, worker_id, source.department_id, procedure)
        common = {
            "session": session,
            "source": source,
            "production_item": production_item,
            "procedure": procedure,
            "quantity": quantity,
            "worker_id": worker_id,
            "remark": remark,
        }
        if procedure.procedure_type == "standard":
            order = create_standard_order(**common)
        elif procedure.procedure_type == "purchase_receipt":
            order = create_purchase_order(**common)
        else:
            raise DomainError("work_order_procedure_type_invalid", "当前工艺不支持开工单")
        mark_order_planned(session, production_item)
        order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
        session.flush()
        return serialize_work_order(session, order)


def submit_work_order(
    work_order_id: int,
    quantity: int,
    completion_action: str,
    user_department: str,
    actor_username: str,
) -> dict:
    if completion_action not in {"direct", "qc"}:
        raise DomainError("completion_action_invalid", "请选择直接填写结果或送QC")
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        before = capture_operation_state(session, order)
        ready_quantity = order.processed_quantity - order.completed_quantity
        if order.work_order_type in {"standard", "assembly"}:
            if order.completed_quantity != 0 or quantity != order.quantity:
                raise DomainError("work_order_full_quantity_required", "工单必须一次处理全部数量")
            order.processed_quantity = order.quantity
            ready_quantity = order.quantity
        else:
            if order.processed_quantity != order.quantity or order.completed_quantity != 0 or quantity != order.quantity:
                raise DomainError("work_order_full_quantity_required", "外购工单必须全部到货后整单填写结果或送检")
        if quantity <= 0 or quantity > ready_quantity:
            raise DomainError("work_order_result_quantity_exceeded", "处理数量超过工单可处理数量")

        if order.work_order_type == "assembly":
            submit_assembly_work_order(session, order, quantity, completion_action, user_department)
            record_undoable_operation(
                session, order, before,
                operation_type="submission",
                operation_label="撤回装配送检" if completion_action == "qc" else "撤回装配加工结果",
                department_code="assembly",
                actor_username=actor_username,
            )
            return serialize_work_order(session, order)
        if order.work_order_type not in {"standard", "purchase_receipt"}:
            raise DomainError("work_order_type_invalid", "工单类型无效")

        source, production_item = load_order_source(session, order)
        if order.source_flow_node_id is None or source.source_flow_node_id != order.source_flow_node_id:
            raise DomainError("work_order_source_snapshot_invalid", "工单来源快照与当前物料位置不一致")
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)
        context, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, order.procedure_id)
        if procedure is None or procedure.workshop_id != node.get("workshop_id"):
            raise DomainError("procedure_not_found", "工单工艺不属于当前车间")

        common = {
            "session": session,
            "order": order,
            "source": source,
            "production_item": production_item,
            "procedure": procedure,
            "node": node,
            "quantity": quantity,
            "completion_action": completion_action,
        }
        if order.work_order_type == "standard":
            submit_standard_order(**common)
        else:
            if completion_action == "qc" and process_qc_node(context.flow, context.nodes, node["id"]) is None:
                raise DomainError("work_order_qc_not_configured", "当前外购节点未配置QC")
            submit_purchase_order(context=context, **common)
        record_undoable_operation(
            session, order, before,
            operation_type="submission",
            operation_label="撤回送检" if completion_action == "qc" else "撤回加工结果",
            department_code=department.department_code,
            actor_username=actor_username,
        )
        return serialize_work_order(session, order)


def register_purchase_arrival(work_order_id: int, quantity: int, user_department: str, actor_username: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open" or order.work_order_type != "purchase_receipt":
            raise DomainError("purchase_arrival_order_invalid", "只有开放的外购工单可以登记到货")
        before = capture_operation_state(session, order)
        remaining = order.quantity - order.processed_quantity
        if quantity <= 0 or quantity > remaining:
            raise DomainError("work_order_processing_quantity_exceeded", "到货数量超过工单待到货数量")
        source, production_item = load_order_source(session, order)
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)
        order.processed_quantity += quantity
        session.flush()
        record_undoable_operation(
            session, order, before,
            operation_type="purchase_arrival",
            operation_label="撤回到货登记",
            department_code=department.department_code,
            actor_username=actor_username,
        )
        return serialize_work_order(session, order)


def resubmit_work_order_rework_batch(batch_id: int, quantity: int, user_department: str, actor_username: str) -> dict:
    with SessionLocal() as session:
        work_order_type = session.scalar(
            select(WorkOrder.work_order_type)
            .join(WorkOrderBatch, WorkOrderBatch.work_order_id == WorkOrder.id)
            .where(WorkOrderBatch.id == batch_id)
        )
    if work_order_type == "assembly":
        return resubmit_assembly_rework_batch(batch_id, quantity, user_department, actor_username)
    return resubmit_standard_rework_batch(batch_id, quantity, user_department, actor_username)


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.work_order_type == "assembly":
            restore_cancelled_assembly_materials(session, order)
        cancel_open_order(session, order, user_department, utc_now())
        return serialize_work_order(session, order)
