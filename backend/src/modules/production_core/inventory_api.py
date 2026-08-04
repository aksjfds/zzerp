"""Accept cross-order stock issued to a confirmed production plan."""

from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.model_api import Department
from modules.production_core.flow import load_product_flow, normal_target
from modules.production_core.movements import record_movement
from modules.production_core.persistence import ProductionItem, Repository
from modules.production_core.work_order_support import (
    move_to_node,
    refresh_order_closed,
    terminal_unit_quantity,
)
from modules.sales.model_api import CustomerOrderItem


def accept_issued_inventory(
    session,
    plan_item,
    quantity: int,
    actor_username: str,
) -> None:
    if quantity <= 0:
        return
    order_item = session.get(CustomerOrderItem, plan_item.customer_order_item_id)
    if order_item is None:
        raise DomainError("customer_order_item_not_found", "订单产品不存在", status_code=409)
    flow, nodes = load_product_flow(session, plan_item.product_id, plan_item.product_version)
    if plan_item.item_type == "finished_product":
        _accept_finished(
            session,
            plan_item,
            order_item,
            flow,
            nodes,
            quantity,
            actor_username,
        )
        return
    if plan_item.item_type == "part":
        target, source_node_id = _part_assembly_target(flow, nodes, plan_item.flow_node_id)
    else:
        target, source_node_id = _assembly_target(flow, nodes, plan_item.flow_node_id)
    if target is None:
        raise DomainError("inventory_issue_target_missing", "库存项目没有可进入的后续节点", status_code=409)
    production_item = _load_or_create_production_item(session, plan_item)
    if target.get("type") == "shipping":
        department_id = move_to_node(
            session,
            production_item,
            target,
            quantity,
            source_node_id,
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
        refresh_order_closed(session, production_item, actor_username)
        return
    if target.get("type") != "assembly":
        raise DomainError("inventory_issue_target_invalid", "库存只能进入装配节点或成品节点", status_code=409)
    department_id = _department_id(session, "assembly")
    repository = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item.id,
            Repository.flow_node_id == target["id"],
            Repository.source_flow_node_id == source_node_id,
            Repository.department_id == department_id,
        )
        .with_for_update()
    )
    if repository is None:
        session.add(Repository(
            production_item_id=production_item.id,
            flow_node_id=target["id"],
            source_flow_node_id=source_node_id,
            department_id=department_id,
            quantity=quantity,
        ))
    else:
        repository.quantity += quantity
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


def _accept_finished(
    session,
    plan_item,
    order_item,
    flow,
    nodes,
    quantity: int,
    actor_username: str,
) -> None:
    shipping = nodes.get(plan_item.flow_node_id)
    if shipping is None or shipping.get("type") != "shipping":
        raise DomainError("inventory_finished_identity_invalid", "成品库存身份与流程图不一致", status_code=409)
    unit_quantity = terminal_unit_quantity(session, flow, nodes, shipping["id"])
    if unit_quantity is None:
        raise DomainError("inventory_finished_unit_invalid", "无法确定成品库存单位", status_code=409)
    incoming = [
        edge.get("source_node_id")
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == shipping["id"]
    ]
    if len(incoming) != 1 or not incoming[0]:
        raise DomainError("inventory_finished_route_invalid", "成品节点必须有唯一来源", status_code=409)
    production_item = ProductionItem(
        customer_order_item_id=order_item.id,
        product_id=plan_item.product_id,
        product_version=plan_item.product_version,
        product_bom_id=None,
        origin_flow_node_id=shipping["id"],
    )
    session.add(production_item)
    session.flush()
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity * unit_quantity,
        movement_type="inventory_issue",
        source_flow_node_id=incoming[0],
        target_flow_node_id=shipping["id"],
        source_department_id=_department_id(session, "finished"),
        target_department_id=_department_id(session, "finished"),
    )
    from modules.inventory.finished_goods_api import allocate_issued_finished_goods
    allocate_issued_finished_goods(
        session,
        production_item=production_item,
        shipping_node_id=shipping["id"],
        quantity=quantity * unit_quantity,
        actor_username=actor_username,
    )
    refresh_order_closed(session, production_item, actor_username)


def _load_or_create_production_item(session, plan_item) -> ProductionItem:
    condition = [
        ProductionItem.customer_order_item_id == plan_item.customer_order_item_id,
        ProductionItem.product_id == plan_item.product_id,
        ProductionItem.product_version == plan_item.product_version,
        ProductionItem.origin_flow_node_id == plan_item.flow_node_id,
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
            origin_flow_node_id=plan_item.flow_node_id,
        )
        session.add(production_item)
        session.flush()
    return production_item


def _part_assembly_target(flow, nodes, origin_node_id: str):
    current_id = origin_node_id
    visited: set[str] = set()
    while current_id not in visited:
        visited.add(current_id)
        target = normal_target(flow, nodes, current_id)
        if target is None:
            return None, current_id
        if target.get("type") == "assembly":
            return target, current_id
        current_id = target["id"]
    return None, current_id


def _assembly_target(flow, nodes, origin_node_id: str):
    target = normal_target(flow, nodes, origin_node_id)
    source_node_id = origin_node_id
    if target and target.get("type") == "qc":
        source_node_id = target["id"]
        target = normal_target(flow, nodes, target["id"])
    return target, source_node_id


def _department_id(session, code: str) -> int:
    department_id = session.scalar(select(Department.id).where(Department.department_code == code))
    if department_id is None:
        raise DomainError("department_not_found", "目标部门不存在", status_code=409)
    return department_id


__all__ = ["accept_issued_inventory"]
