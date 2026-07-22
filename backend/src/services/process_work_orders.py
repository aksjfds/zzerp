from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now, utc_now
from models.organization import Department, Procedure
from models.production import WorkOrder, WorkOrderBatch
from services.assembly_work_orders import (
    resubmit_assembly_rework_batch,
    submit_assembly_work_order,
)
from services.errors import DomainError
from services.procedure_tags import procedure_department_id
from services.purchase_work_orders import (
    create_purchase_order,
    submit_purchase_order,
)
from services.tag_work_orders import (
    create_tag_order,
    resubmit_tag_rework_batch,
    submit_tag_order,
)
from services.work_order_command_support import (
    cancel_open_order,
    load_order_source,
    load_source,
    validate_worker,
)
from services.work_order_presenters import serialize_work_order
from services.work_order_support import mark_order_planned, node_context
from services.production_flow import process_qc_node
from services.production_operation_undo import (
    capture_operation_state,
    record_undoable_operation,
)


def create_work_order(
    repository_id: int | None,
    procedure_tag_stock_id: int | None,
    tag_names: list[str],
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    if (repository_id is None) == (procedure_tag_stock_id is None):
        raise DomainError("work_order_source_invalid", "工单必须且只能选择一个库存来源")
    with SessionLocal.begin() as session:
        source, production_item = load_source(
            session,
            repository_id,
            procedure_tag_stock_id,
        )
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)
        _, node = node_context(session, production_item, source.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有工艺节点可以开工单")
        procedure = session.get(
            Procedure,
            node.get("procedure_id"),
            with_for_update=True,
        )
        if procedure is None:
            raise DomainError("procedure_not_found", "当前流程工艺不存在")
        if source.department_id != procedure_department_id(session, procedure):
            raise DomainError("work_order_source_department_invalid", "工单来源不属于当前工艺部门")
        validate_worker(session, worker_id, source.department_id, procedure)

        common = {
            "session": session,
            "source": source,
            "production_item": production_item,
            "procedure": procedure,
            "tag_names": tag_names,
            "quantity": quantity,
            "worker_id": worker_id,
        }
        if procedure.procedure_type == "standard":
            order = create_tag_order(**common)
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
        raise DomainError("completion_action_invalid", "请选择直接完成或送 QC")
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        before = capture_operation_state(session, order)
        if order.work_order_type == "assembly":
            submit_assembly_work_order(
                session,
                order,
                quantity,
                completion_action,
                user_department,
            )
            record_undoable_operation(
                session,
                order,
                before,
                operation_type="submission",
                operation_label="撤回装配送检" if completion_action == "qc" else "撤回装配完成",
                department_code="assembly",
                actor_username=actor_username,
            )
            return serialize_work_order(session, order)
        if order.work_order_type not in {"tag", "purchase_receipt"}:
            raise DomainError("work_order_type_invalid", "工单类型无效")

        source, production_item = load_order_source(session, order)
        if (
            order.source_flow_node_id is None
            or source.source_flow_node_id != order.source_flow_node_id
        ):
            raise DomainError(
                "work_order_source_snapshot_invalid",
                "工单来源快照与当前库存位置不一致",
            )
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)

        context, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None or order.procedure_id != procedure.id:
            raise DomainError("procedure_not_found", "工单所属工艺不存在")
        if order.work_order_type == "purchase_receipt":
            qc_required = process_qc_node(
                context.flow,
                context.nodes,
                node["id"],
            ) is not None
            if completion_action == "qc" and not qc_required:
                raise DomainError("work_order_qc_not_configured", "当前外购工艺未配置 QC")
            if completion_action == "direct" and qc_required:
                raise DomainError("work_order_qc_required", "当前外购工艺必须送 QC")

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
        if order.work_order_type == "tag":
            submit_tag_order(**common)
        else:
            submit_purchase_order(context=context, **common)
        record_undoable_operation(
            session,
            order,
            before,
            operation_type="submission",
            operation_label=(
                "撤回送检"
                if completion_action == "qc"
                else "撤回直接完成"
            ),
            department_code=department.department_code,
            actor_username=actor_username,
        )
        return serialize_work_order(session, order)


def resubmit_work_order_rework_batch(
    batch_id: int,
    quantity: int,
    user_department: str,
    actor_username: str,
) -> dict:
    with SessionLocal() as session:
        work_order_type = session.scalar(
            select(WorkOrder.work_order_type)
            .join(WorkOrderBatch, WorkOrderBatch.work_order_id == WorkOrder.id)
            .where(WorkOrderBatch.id == batch_id)
        )
    if work_order_type == "assembly":
        return resubmit_assembly_rework_batch(
            batch_id, quantity, user_department, actor_username
        )
    return resubmit_tag_rework_batch(
        batch_id, quantity, user_department, actor_username
    )


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        cancel_open_order(session, order, user_department, utc_now())
        return serialize_work_order(session, order)
