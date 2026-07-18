from sqlalchemy import func, select

from database import SessionLocal
from models.organization import Department, Procedure, ProcedureSubstep
from models.production import ProcedureStageStock, ProductionItem, WorkOrder
from services.errors import DomainError
from services.procedure_stages import consume_stage_stock
from services.production_movements import record_movement
from services.work_order_support import move_to_node, node_context, refresh_order_closed


def dispatch_stage_stock(
    stage_stock_id: int,
    quantity: int,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        identity = session.execute(
            select(
                ProcedureStageStock.id,
                ProcedureStageStock.production_item_id,
            ).where(ProcedureStageStock.id == stage_stock_id)
        ).one_or_none()
        if identity is None:
            raise DomainError(
                "procedure_stage_stock_not_found",
                "细分工序已完数量不存在",
                status_code=404,
            )
        production_item = session.get(
            ProductionItem,
            identity.production_item_id,
            with_for_update=True,
        )
        stock = session.get(
            ProcedureStageStock,
            stage_stock_id,
            with_for_update=True,
            populate_existing=True,
        )
        if stock is None:
            raise DomainError(
                "procedure_stage_stock_not_found",
                "细分工序已完数量不存在",
                status_code=404,
            )
        department = session.get(Department, stock.department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)

        substep = session.get(ProcedureSubstep, stock.completed_substep_id)
        procedure = session.get(Procedure, substep.procedure_id) if substep else None
        if production_item is None or substep is None or procedure is None:
            raise DomainError("production_context_missing", "细分工序出货资料不完整")
        if procedure.procedure_type != "standard":
            raise DomainError("procedure_dispatch_not_allowed", "当前工艺不支持手动出货")

        context, node = node_context(session, production_item, stock.flow_node_id)
        if node.get("type") != "process" or node.get("procedure_id") != procedure.id:
            raise DomainError("procedure_stage_mismatch", "细分工序数量不属于当前流程工艺")

        reserved = session.scalar(
            select(func.coalesce(func.sum(WorkOrder.quantity - WorkOrder.completed_quantity), 0))
            .where(
                WorkOrder.procedure_stage_stock_id == stock.id,
                WorkOrder.status == "open",
            )
        ) or 0
        available = stock.quantity - int(reserved)
        if quantity > available:
            raise DomainError("procedure_dispatch_quantity_exceeded", "出货数量超过当前可用已完数量")

        target = context.normal_target(node["id"])
        target_department_id = move_to_node(
            session,
            production_item,
            target,
            quantity,
            node["id"],
        )
        target_flow_node_id = target.get("id") if target else None
        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="procedure_dispatch",
            source_flow_node_id=node["id"],
            target_flow_node_id=target_flow_node_id,
            source_department_id=stock.department_id,
            target_department_id=target_department_id,
        )
        consume_stage_stock(session, stock, quantity)
        session.flush()
        refresh_order_closed(session, production_item)
        return {
            "stage_stock_id": stage_stock_id,
            "production_item_id": production_item.id,
            "substep_id": substep.id,
            "quantity": quantity,
            "target_flow_node_id": target_flow_node_id,
            "target_department_id": target_department_id,
        }
