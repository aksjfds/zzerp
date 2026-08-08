"""Order-owned finished goods receiving, shipment, and surplus transfer."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.time import utc_now
from modules.engineering.model_api import Product
from modules.errors import DomainError
from modules.inventory.identity import inventory_identity_key
from modules.inventory.ownership_api import confirm_receipt, create_receipt
from modules.inventory.persistence import FinishedOrderStock
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.model_api import ProductionItem, ProductionMovement
from modules.production_core.operational_api import (
    load_product_flow,
    record_movement,
    refresh_order_closed,
    terminal_unit_quantity,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


SHIPMENT_MOVEMENT_TYPES = ("customer_shipment",)


def register_pending_finished_goods(
    session: Session,
    *,
    production_item: ProductionItem,
    shipping_node_id: str,
    quantity: int,
) -> FinishedOrderStock:
    if quantity <= 0:
        raise DomainError("finished_goods_quantity_invalid", "成品数量必须大于0")
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    if order_item is None:
        raise DomainError("customer_order_item_not_found", "订单产品不存在", status_code=409)
    order = session.get(CustomerOrder, order_item.customer_order_id)
    product = session.get(Product, order_item.product_id)
    flow, nodes = load_product_flow(session, order_item.product_id, order_item.product_version)
    shipping = nodes.get(shipping_node_id)
    unit_quantity = terminal_unit_quantity(session, flow, nodes, shipping_node_id)
    if order is None or product is None or shipping is None or shipping.get("type") != "shipping":
        raise DomainError("finished_goods_context_invalid", "成品入库资料不完整", status_code=409)
    if unit_quantity is None:
        raise DomainError("finished_goods_unit_invalid", "无法确定成品计量单位", status_code=409)
    if quantity % unit_quantity:
        raise DomainError(
            "finished_goods_unit_incomplete",
            f"放行到成品部的数量必须是每件产品用量 {unit_quantity} 的整数倍",
        )
    lot = session.scalar(
        select(FinishedOrderStock)
        .where(
            FinishedOrderStock.production_item_id == production_item.id,
            FinishedOrderStock.flow_node_id == shipping_node_id,
        )
        .with_for_update()
    )
    if lot is None:
        lot = FinishedOrderStock(
            customer_order_id=order.id,
            customer_order_item_id=order_item.id,
            production_item_id=production_item.id,
            product_id=order_item.product_id,
            product_version=order_item.product_version,
            flow_node_id=shipping_node_id,
            item_code=product.factory_code,
            item_name=product.product_name,
            unit_quantity=unit_quantity,
            pending_quantity=quantity,
        )
        session.add(lot)
    else:
        lot.pending_quantity += quantity
        lot.revision += 1
        lot.updated_at = utc_now()
    session.flush()
    return lot


def allocate_issued_finished_goods(
    session: Session,
    *,
    production_item: ProductionItem,
    shipping_node_id: str,
    quantity: int,
    actor_username: str,
) -> FinishedOrderStock:
    """Turn cross-order finished inventory into order-owned, shippable stock."""
    lot = register_pending_finished_goods(
        session,
        production_item=production_item,
        shipping_node_id=shipping_node_id,
        quantity=quantity,
    )
    lot.pending_quantity -= quantity
    lot.available_quantity += quantity
    lot.received_at = utc_now()
    lot.received_by = actor_username
    lot.revision += 1
    lot.updated_at = utc_now()
    session.flush()
    return lot


def list_finished_order_stocks(operation: str) -> list[dict]:
    with SessionLocal() as session:
        statement = select(FinishedOrderStock).join(
            CustomerOrder,
            CustomerOrder.id == FinishedOrderStock.customer_order_id,
        )
        if operation == "receipt":
            statement = statement.where(
                CustomerOrder.status.in_(("planned", "closed")),
                FinishedOrderStock.pending_quantity > 0,
            )
        elif operation == "shipment":
            statement = statement.where(
                CustomerOrder.status == "planned",
                FinishedOrderStock.available_quantity > 0,
            )
        else:
            statement = statement.where(
                (CustomerOrder.status == "planned")
                | (
                    (CustomerOrder.status == "closed")
                    & (FinishedOrderStock.pending_quantity > 0)
                )
            )
        lots = list(session.scalars(
            statement.order_by(
                FinishedOrderStock.customer_order_id,
                FinishedOrderStock.customer_order_item_id,
                FinishedOrderStock.id,
            )
        ))
        groups: dict[int, list[FinishedOrderStock]] = defaultdict(list)
        for lot in lots:
            groups[lot.customer_order_item_id].append(lot)
        rows = []
        for order_item_id, item_lots in groups.items():
            order_item = session.get(CustomerOrderItem, order_item_id)
            order = session.get(CustomerOrder, item_lots[0].customer_order_id)
            if order_item is None or order is None:
                continue
            unit_quantity = item_lots[0].unit_quantity
            shipped_raw = _shipped_raw_quantity(session, order_item_id, item_lots[0].flow_node_id)
            rows.append({
                "customer_order_id": order.id,
                "customer_order_no": order.customer_order_no,
                "order_status": order.status,
                "customer_order_item_id": order_item.id,
                "item_code": item_lots[0].item_code,
                "item_name": item_lots[0].item_name,
                "product_version": item_lots[0].product_version,
                "required_quantity": order_item.quantity,
                "pending_quantity": sum(item.pending_quantity for item in item_lots) // unit_quantity,
                "available_quantity": sum(item.available_quantity for item in item_lots) // unit_quantity,
                "shipped_quantity": shipped_raw // unit_quantity,
                "outstanding_quantity": max(order_item.quantity - shipped_raw // unit_quantity, 0),
            })
        return rows


def confirm_finished_order_receipt(customer_order_item_id: int, actor_username: str) -> dict:
    result = None
    with SessionLocal.begin() as session:
        lots = list(session.scalars(
            select(FinishedOrderStock)
            .where(
                FinishedOrderStock.customer_order_item_id == customer_order_item_id,
                FinishedOrderStock.pending_quantity > 0,
            )
            .order_by(FinishedOrderStock.id)
            .with_for_update()
        ))
        if not lots:
            raise DomainError("finished_goods_pending_not_found", "没有待确认入库的成品", status_code=404)
        customer_order = session.get(CustomerOrder, lots[0].customer_order_id, with_for_update=True)
        if customer_order is None:
            raise DomainError("customer_order_not_found", "客户订单不存在", status_code=409)
        finished_department_id = _finished_department_id(session)
        refresh_item = None
        for lot in lots:
            quantity = lot.pending_quantity
            lot.pending_quantity = 0
            lot.available_quantity += quantity
            lot.received_at = utc_now()
            lot.received_by = actor_username
            lot.revision += 1
            lot.updated_at = utc_now()
            production_item = session.get(ProductionItem, lot.production_item_id)
            if production_item is None:
                raise DomainError("production_item_not_found", "成品生产记录不存在", status_code=409)
            record_movement(
                session,
                production_item=production_item,
                quantity=quantity,
                movement_type="finished_receipt",
                source_flow_node_id=lot.flow_node_id,
                target_flow_node_id=lot.flow_node_id,
                source_department_id=finished_department_id,
                target_department_id=finished_department_id,
            )
            refresh_item = production_item
        session.flush()
        if refresh_item is not None:
            refresh_order_closed(session, refresh_item, actor_username)
        if customer_order.status == "closed":
            transfer_order_finished_surplus(session, customer_order, actor_username)
        session.flush()
        result = _serialize_order_item(session, customer_order_item_id)
    return result


def ship_finished_order_item(
    customer_order_item_id: int,
    quantity: int,
    actor_username: str,
) -> dict:
    if quantity <= 0:
        raise DomainError("finished_shipment_quantity_invalid", "发货数量必须大于0")
    result = None
    with SessionLocal.begin() as session:
        order_item = session.get(CustomerOrderItem, customer_order_item_id, with_for_update=True)
        if order_item is None:
            raise DomainError("customer_order_item_not_found", "订单产品不存在", status_code=404)
        order = session.get(CustomerOrder, order_item.customer_order_id, with_for_update=True)
        if order is None or order.status != "planned":
            raise DomainError("customer_order_not_shippable", "当前订单不能发货", status_code=409)
        lots = list(session.scalars(
            select(FinishedOrderStock)
            .where(
                FinishedOrderStock.customer_order_item_id == customer_order_item_id,
                FinishedOrderStock.available_quantity > 0,
            )
            .order_by(FinishedOrderStock.id)
            .with_for_update()
        ))
        if not lots:
            raise DomainError("finished_goods_unavailable", "成品部没有可发货数量", status_code=409)
        unit_quantity = lots[0].unit_quantity
        shipped_products = _shipped_raw_quantity(session, order_item.id, lots[0].flow_node_id) // unit_quantity
        outstanding = max(order_item.quantity - shipped_products, 0)
        if quantity > outstanding:
            raise DomainError("finished_shipment_exceeds_order", "发货数量不能超过订单剩余需求")
        required_raw = quantity * unit_quantity
        if sum(item.available_quantity for item in lots) < required_raw:
            raise DomainError("finished_goods_unavailable", "成品部可发货数量不足", status_code=409)
        remaining = required_raw
        finished_department_id = _finished_department_id(session)
        refresh_item = None
        for lot in lots:
            allocated = min(lot.available_quantity, remaining)
            if allocated <= 0:
                continue
            lot.available_quantity -= allocated
            lot.shipped_quantity += allocated
            lot.last_shipped_at = utc_now()
            lot.last_shipped_by = actor_username
            lot.revision += 1
            lot.updated_at = utc_now()
            production_item = session.get(ProductionItem, lot.production_item_id)
            if production_item is None:
                raise DomainError("production_item_not_found", "成品生产记录不存在", status_code=409)
            record_movement(
                session,
                production_item=production_item,
                quantity=allocated,
                movement_type="customer_shipment",
                source_flow_node_id=lot.flow_node_id,
                target_flow_node_id=lot.flow_node_id,
                source_department_id=finished_department_id,
                target_department_id=finished_department_id,
            )
            refresh_item = production_item
            remaining -= allocated
            if remaining == 0:
                break
        session.flush()
        if refresh_item is not None:
            refresh_order_closed(session, refresh_item, actor_username)
        session.flush()
        result = _serialize_order_item(session, customer_order_item_id)
    return result


def transfer_order_finished_surplus(
    session: Session,
    customer_order,
    actor_username: str,
) -> None:
    lots = list(session.scalars(
        select(FinishedOrderStock)
        .where(
            FinishedOrderStock.customer_order_id == customer_order.id,
            FinishedOrderStock.available_quantity > 0,
        )
        .order_by(FinishedOrderStock.id)
        .with_for_update()
    ))
    for lot in lots:
        if lot.available_quantity % lot.unit_quantity:
            raise DomainError("finished_surplus_unit_invalid", "成品结余不是完整产品数量", status_code=409)
        product_quantity = lot.available_quantity // lot.unit_quantity
        if product_quantity <= 0:
            continue
        receipt = create_receipt(
            session,
            identity_key=inventory_identity_key(
                department_code="finished",
                item_type="finished_product",
                product_id=lot.product_id,
                product_version=lot.product_version,
                product_bom_id=None,
                flow_node_id=lot.flow_node_id,
                completed_flow_node_id=lot.flow_node_id,
            ),
            department_code="finished",
            item_type="finished_product",
            product_id=lot.product_id,
            product_version=lot.product_version,
            product_bom_id=None,
            flow_node_id=lot.flow_node_id,
            completed_flow_node_id=lot.flow_node_id,
            item_code=lot.item_code,
            item_name=lot.item_name,
            quantity=product_quantity,
            source_customer_order_id=customer_order.id,
            source_production_item_id=lot.production_item_id,
        )
        confirm_receipt(session, receipt.id, actor_username, "订单成品结余自动入库")
        lot.transferred_quantity += lot.available_quantity
        lot.available_quantity = 0
        lot.revision += 1
        lot.updated_at = utc_now()


def _serialize_order_item(session: Session, customer_order_item_id: int) -> dict:
    lots = list(session.scalars(
        select(FinishedOrderStock)
        .where(FinishedOrderStock.customer_order_item_id == customer_order_item_id)
        .order_by(FinishedOrderStock.id)
    ))
    order_item = session.get(CustomerOrderItem, customer_order_item_id)
    order = session.get(CustomerOrder, order_item.customer_order_id) if order_item else None
    if not lots or order_item is None or order is None:
        raise DomainError("finished_order_stock_not_found", "订单成品记录不存在", status_code=404)
    unit_quantity = lots[0].unit_quantity
    shipped_raw = _shipped_raw_quantity(session, customer_order_item_id, lots[0].flow_node_id)
    return {
        "customer_order_id": order.id,
        "customer_order_no": order.customer_order_no,
        "order_status": order.status,
        "customer_order_item_id": order_item.id,
        "item_code": lots[0].item_code,
        "item_name": lots[0].item_name,
        "product_version": lots[0].product_version,
        "required_quantity": order_item.quantity,
        "pending_quantity": sum(item.pending_quantity for item in lots) // unit_quantity,
        "available_quantity": sum(item.available_quantity for item in lots) // unit_quantity,
        "shipped_quantity": shipped_raw // unit_quantity,
        "outstanding_quantity": max(order_item.quantity - shipped_raw // unit_quantity, 0),
    }


def _shipped_raw_quantity(session: Session, order_item_id: int, shipping_node_id: str) -> int:
    return int(session.scalar(
        select(func.coalesce(func.sum(ProductionMovement.quantity), 0))
        .join(ProductionItem, ProductionItem.id == ProductionMovement.production_item_id)
        .where(
            ProductionItem.customer_order_item_id == order_item_id,
            ProductionMovement.movement_type.in_(SHIPMENT_MOVEMENT_TYPES),
            ProductionMovement.target_flow_node_id == shipping_node_id,
        )
    ) or 0)


def _finished_department_id(session: Session) -> int:
    department_id = get_department_ids_by_codes(session, {"finished"}).get("finished")
    if department_id is None:
        raise DomainError("department_not_found", "成品部不存在", status_code=409)
    return department_id


__all__ = [
    "allocate_issued_finished_goods",
    "confirm_finished_order_receipt",
    "list_finished_order_stocks",
    "register_pending_finished_goods",
    "ship_finished_order_item",
    "transfer_order_finished_surplus",
]
