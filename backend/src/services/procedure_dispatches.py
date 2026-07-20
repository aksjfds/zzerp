from sqlalchemy import func, select

from database import SessionLocal
from models.organization import Department, Procedure, ProcedureTagSet
from models.production import ProcedureTagStock, ProductionItem, WorkOrder
from services.errors import DomainError
from services.procedure_tags import consume_tag_stock
from services.production_movements import record_movement
from services.work_order_support import move_to_node, node_context, refresh_order_closed
from services.work_order_progress import order_remaining_expression


def dispatch_tag_stock(
    tag_stock_id: int,
    quantity: int,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        identity = session.execute(
            select(
                ProcedureTagStock.id,
                ProcedureTagStock.production_item_id,
            ).where(ProcedureTagStock.id == tag_stock_id)
        ).one_or_none()
        if identity is None:
            raise DomainError(
                "procedure_tag_stock_not_found",
                "标记组合已完数量不存在",
                status_code=404,
            )
        production_item = session.get(
            ProductionItem,
            identity.production_item_id,
            with_for_update=True,
        )
        stock = session.get(
            ProcedureTagStock,
            tag_stock_id,
            with_for_update=True,
            populate_existing=True,
        )
        if stock is None:
            raise DomainError(
                "procedure_tag_stock_not_found",
                "标记组合已完数量不存在",
                status_code=404,
            )
        department = session.get(Department, stock.department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)

        tag_set = session.get(ProcedureTagSet, stock.tag_set_id)
        if production_item is None or tag_set is None:
            raise DomainError("production_context_missing", "标记组合出货资料不完整")
        procedure = session.get(Procedure, tag_set.procedure_id)
        if procedure.procedure_type != "standard":
            raise DomainError("procedure_dispatch_not_allowed", "当前工艺不支持手动出货")

        context, node = node_context(session, production_item, stock.flow_node_id)
        if node.get("type") != "process" or node.get("procedure_id") != procedure.id:
            raise DomainError("procedure_tag_mismatch", "标记组合数量不属于当前流程工艺")

        reserved = session.scalar(
            select(func.coalesce(func.sum(order_remaining_expression()), 0))
            .where(
                WorkOrder.procedure_tag_stock_id == stock.id,
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
            source_tag_set_id=tag_set.id,
            source_department_id=stock.department_id,
            target_department_id=target_department_id,
        )
        consume_tag_stock(session, stock, quantity)
        session.flush()
        refresh_order_closed(session, production_item)
        return {
            "tag_stock_id": tag_stock_id,
            "production_item_id": production_item.id,
            "tag_set_id": tag_set.id,
            "quantity": quantity,
            "target_flow_node_id": target_flow_node_id,
            "target_department_id": target_department_id,
        }
