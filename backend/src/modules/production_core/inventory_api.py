"""Inject material stock issued during plan confirmation into production."""

from sqlalchemy import select

from domain.production_inventory import IssuedInventoryStock, IssuedPlanItem
from modules.errors import DomainError
from modules.organization.model_api import Department
from modules.production_core.flow import load_product_flow
from modules.production_core.material_state_api import get_material_state
from modules.production_core.movements import record_movement
from modules.production_core.persistence import ProductionItem
from modules.production_core.work_order_support import move_to_node
from modules.sales.model_api import CustomerOrderItem


def accept_issued_inventory(
    session,
    plan_item: IssuedPlanItem,
    issued_stock: IssuedInventoryStock,
    _actor_username: str,
) -> None:
    quantity = issued_stock.quantity
    if quantity <= 0:
        return
    order_item = session.get(CustomerOrderItem, plan_item.customer_order_item_id)
    if order_item is None:
        raise DomainError("customer_order_item_not_found", "订单产品不存在", status_code=409)
    _flow, nodes = load_product_flow(session, plan_item.product_id, plan_item.product_version)
    if plan_item.item_type == "finished_product":
        raise DomainError(
            "finished_stock_reservation_injected",
            "成品库存占用不能作为生产物料注入",
            status_code=409,
        )
    processing_state = get_material_state(session, issued_stock.processing_state_id)
    if (
        processing_state.resume_flow_node_id != issued_stock.resume_flow_node_id
        or processing_state.product_id != plan_item.product_id
        or processing_state.product_version != plan_item.product_version
        or processing_state.product_bom_id != plan_item.product_bom_id
        or processing_state.origin_flow_node_id != plan_item.flow_node_id
    ):
        raise DomainError(
            "inventory_processing_state_changed",
            "库存加工状态与出库记录不一致",
            status_code=409,
        )
    target = nodes.get(processing_state.resume_flow_node_id)
    source_node_id = processing_state.completed_flow_node_id
    if target is None:
        raise DomainError("inventory_issue_target_missing", "库存项目没有可进入的后续节点", status_code=409)
    production_item = _load_or_create_production_item(
        session,
        plan_item,
        issued_stock.flow_node_id,
    )
    if target.get("type") == "finished_inbound":
        raise DomainError(
            "warehouse_material_finished_route_invalid",
            "配件或装配体库存不能在生产计划确认时直接转为成品",
            status_code=409,
        )
    department_id = move_to_node(
        session,
        production_item,
        target,
        quantity,
        source_node_id,
        processing_state_id=processing_state.id,
    )
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="inventory_issue",
        source_flow_node_id=source_node_id,
        target_flow_node_id=target["id"],
        source_department_id=_department_id(session, "warehouse"),
        target_department_id=department_id,
    )

def _load_or_create_production_item(
    session,
    plan_item,
    origin_flow_node_id: str,
) -> ProductionItem:
    condition = [
        ProductionItem.customer_order_item_id == plan_item.customer_order_item_id,
        ProductionItem.product_id == plan_item.product_id,
        ProductionItem.product_version == plan_item.product_version,
        ProductionItem.origin_flow_node_id == origin_flow_node_id,
    ]
    if plan_item.product_bom_id is None:
        condition.append(ProductionItem.product_bom_id.is_(None))
    else:
        condition.append(ProductionItem.product_bom_id == plan_item.product_bom_id)
    production_item = session.scalar(select(ProductionItem).where(*condition).limit(1))
    if production_item is None:
        production_item = ProductionItem(
            customer_order_item_id=plan_item.customer_order_item_id,
            product_id=plan_item.product_id,
            product_version=plan_item.product_version,
            product_bom_id=plan_item.product_bom_id,
            origin_flow_node_id=origin_flow_node_id,
        )
        session.add(production_item)
        session.flush()
    return production_item


def _department_id(session, code: str) -> int:
    department_id = session.scalar(select(Department.id).where(Department.department_code == code))
    if department_id is None:
        raise DomainError("department_not_found", "目标部门不存在", status_code=409)
    return department_id


__all__ = ["accept_issued_inventory"]
