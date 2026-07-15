from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now, utc_now
from models.organization import Department, Procedure, Worker, Workshop
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch
from services.assembly_work_orders import submit_assembly_work_order
from services.errors import DomainError
from services.production_movements import record_movement
from services.work_order_presenters import serialize_work_order
from services.work_order_support import (
    consume_repository,
    mark_order_planned,
    move_to_node,
    node_context,
    refresh_order_closed,
)


def create_work_order(
    repository_id: int,
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        repository = session.get(Repository, repository_id, with_for_update=True)
        if repository is None:
            raise DomainError("repository_not_found", "配件记录不存在", status_code=404)
        department = session.get(Department, repository.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)

        production_item = session.get(ProductionItem, repository.production_item_id)
        _, node = node_context(session, production_item, repository.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有工艺节点可以开工单")
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None:
            raise DomainError("procedure_not_found", "工艺节点未关联有效工艺")
        worker = session.get(Worker, worker_id) if worker_id else None
        if worker_id and (
            worker is None
            or worker.department_id != repository.department_id
            or worker.workshop_id != procedure.workshop_id
        ):
            raise DomainError("worker_invalid", "工人不属于当前工艺所在车间")

        open_orders = session.scalars(
            select(WorkOrder).where(
                WorkOrder.repository_id == repository.id,
                WorkOrder.status == "open",
            )
        ).all()
        reserved = sum(item.quantity - item.completed_quantity for item in open_orders)
        if quantity > repository.quantity - reserved:
            raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")

        order = WorkOrder(
            repository_id=repository.id,
            production_item_id=production_item.id,
            procedure_id=procedure.id,
            procedure_type=procedure.procedure_type,
            procedure_name=procedure.procedure_name,
            flow_node_id=node["id"],
            worker_id=worker_id,
            quantity=quantity,
        )
        session.add(order)
        session.flush()
        mark_order_planned(session, production_item)
        order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
        session.flush()
        return serialize_work_order(session, order)


def submit_work_order(work_order_id: int, quantity: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        if order.procedure_id is None:
            return submit_assembly_work_order(session, order, quantity, user_department)
        if order.repository_id is None:
            raise DomainError("work_order_closed", "工单来源库存已不存在")

        production_item = session.get(
            ProductionItem, order.production_item_id, with_for_update=True
        )
        repository = session.get(Repository, order.repository_id, with_for_update=True)
        if repository is None:
            raise DomainError("repository_not_found", "工单来源库存不存在")
        department = session.get(Department, repository.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)

        remaining = order.quantity - order.completed_quantity
        if quantity > remaining or quantity > repository.quantity:
            raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")
        context, node = node_context(session, production_item, repository.flow_node_id)
        target = context.normal_target(node["id"])
        is_purchase_receipt = order.procedure_type == "purchase_receipt"
        batch = None
        if target is not None and target.get("type") == "qc":
            batch = WorkOrderBatch(
                work_order_id=order.id,
                submitted_quantity=quantity,
                flow_node_id=target["id"],
            )
            session.add(batch)
            session.flush()
            target_department_id = move_to_node(
                session, production_item, target, quantity, node["id"]
            )
        else:
            if quantity != remaining and not is_purchase_receipt:
                raise DomainError("partial_completion_not_allowed", "非 QC 工艺必须一次完成剩余数量")
            target_department_id = move_to_node(
                session, production_item, target, quantity, node["id"]
            )

        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="purchase_receipt" if is_purchase_receipt else "process",
            source_flow_node_id=node["id"],
            target_flow_node_id=target.get("id") if target else None,
            source_department_id=repository.department_id,
            target_department_id=target_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id if batch else None,
        )
        # Persist the submission while the work order is still open; database
        # validation intentionally rejects submissions to closed orders.
        session.flush()
        if repository.quantity == quantity:
            order.repository_id = None
            # Release the composite repository reference before deleting an
            # exhausted repository row.
            session.flush()
        consume_repository(session, repository, quantity)
        order.completed_quantity += quantity
        if quantity == remaining:
            order.status = "closed"
            order.closed_at = utc_now()
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_work_order(session, order)


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_not_cancellable", "只有未完成工单可以取消")
        if order.completed_quantity:
            raise DomainError("work_order_started", "已经提交过产量的工单不能取消")
        procedure = session.get(Procedure, order.procedure_id) if order.procedure_id else None
        workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
        department = session.get(Department, workshop.department_id) if workshop else None
        department_code = department.department_code if department else "assembly"
        if user_department not in {"sys", department_code}:
            raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
        order.status = "cancelled"
        order.closed_at = utc_now()
        session.flush()
        return serialize_work_order(session, order)
