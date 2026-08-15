"""Public API for cross-order inventory queries and production-plan issues."""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from database import SessionLocal
from modules.inventory.persistence import (
    InventoryReservation,
    InventoryStock,
    InventoryTransaction,
)
from modules.inventory.reservation_api import issue_plan_reservations
from modules.organization.model_api import Department
from modules.planning.model_api import ProductionPlan, ProductionPlanItem
from modules.production_core.model_api import ProductionItem, ProductionMovement
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.inventory.persistence import FinishedOrderStock
from modules.engineering.model_api import ProductBom


def list_stocks(department_code: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        statement = select(InventoryStock).order_by(InventoryStock.item_code, InventoryStock.id)
        if department_code:
            statement = statement.where(InventoryStock.department_code == department_code)
        return [_serialize_stock(session, item) for item in session.scalars(statement)]


def list_transactions(
    department_code: str,
    stock_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(InventoryTransaction)
            .join(InventoryStock, InventoryStock.id == InventoryTransaction.inventory_stock_id)
            .where(InventoryStock.department_code == department_code)
        )
        if stock_id:
            statement = statement.where(InventoryTransaction.inventory_stock_id == stock_id)
        statement = statement.order_by(InventoryTransaction.id.desc()).limit(limit)
        rows = [
            {
                "id": item.id,
                "inventory_stock_id": item.inventory_stock_id,
                "production_plan_id": item.production_plan_id,
                "transaction_type": item.transaction_type,
                "quantity": item.quantity,
                "quantity_before": item.quantity_before,
                "quantity_after": item.quantity_after,
                "reserved_before": item.reserved_before,
                "reserved_after": item.reserved_after,
                "actor_username": item.actor_username,
                "reason": item.reason or "",
                "created_at": item.created_at.isoformat(),
                "item_code": stock.item_code,
                "item_name": stock.item_name,
                "customer_order_no": "",
                "completed_node_label": _completed_node_label(session, stock),
            }
            for item, stock in session.execute(
                statement.add_columns(InventoryStock)
            )
        ]
        if department_code == "finished":
            rows.extend(_finished_order_transactions(session))
        return sorted(
            rows,
            key=lambda item: (item["created_at"], item["id"]),
            reverse=True,
        )[:limit]


def _finished_order_transactions(session: Session) -> list[dict]:
    finished_department_id = session.scalar(
        select(Department.id).where(Department.department_code == "finished")
    )
    movement_filter = ProductionMovement.movement_type.in_(
        ("finished_receipt", "customer_shipment")
    )
    if finished_department_id is not None:
        movement_filter = or_(
            movement_filter,
            and_(
                ProductionMovement.movement_type == "inventory_issue",
                ProductionMovement.source_department_id == finished_department_id,
                ProductionMovement.target_department_id == finished_department_id,
            ),
        )
    statement = (
        select(
            ProductionMovement,
            CustomerOrderItem,
            CustomerOrder,
            FinishedOrderStock,
        )
        .join(ProductionItem, ProductionItem.id == ProductionMovement.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
        .join(
            FinishedOrderStock,
            and_(
                FinishedOrderStock.production_item_id == ProductionItem.id,
                FinishedOrderStock.flow_node_id == ProductionMovement.target_flow_node_id,
            ),
        )
        .where(movement_filter)
        .order_by(ProductionMovement.created_at, ProductionMovement.id)
    )
    balances: dict[int, int] = {}
    rows: list[dict] = []
    for movement, order_item, order, lot in session.execute(statement):
        quantity = movement.quantity // lot.unit_quantity
        if quantity <= 0:
            continue
        before = balances.get(order_item.id, 0)
        is_outbound = movement.movement_type == "customer_shipment"
        after = max(before - quantity, 0) if is_outbound else before + quantity
        balances[order_item.id] = after
        transaction_type = {
            "finished_receipt": "finished_receipt",
            "customer_shipment": "customer_shipment",
            "inventory_issue": "finished_stock_issue",
        }[movement.movement_type]
        rows.append({
            "id": -movement.id,
            "inventory_stock_id": 0,
            "production_plan_id": None,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "quantity_before": before,
            "quantity_after": after,
            "reserved_before": 0,
            "reserved_after": 0,
            "actor_username": "系统记录",
            "reason": f"订单 {order.customer_order_no}",
            "created_at": movement.created_at.isoformat(),
            "item_code": lot.item_code,
            "item_name": lot.item_name,
            "customer_order_no": order.customer_order_no,
        })
    return rows


def list_outbound_plans(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ProductionPlan, CustomerOrder, InventoryReservation, InventoryStock, ProductionPlanItem)
            .join(CustomerOrder, CustomerOrder.id == ProductionPlan.customer_order_id)
            .join(InventoryReservation, InventoryReservation.production_plan_id == ProductionPlan.id)
            .join(InventoryStock, InventoryStock.id == InventoryReservation.inventory_stock_id)
            .join(ProductionPlanItem, ProductionPlanItem.id == InventoryReservation.production_plan_item_id)
            .where(
                ProductionPlan.status == "confirmed",
                InventoryStock.department_code == department_code,
                InventoryReservation.status.in_(("reserved", "issued")),
                InventoryReservation.issued_quantity < InventoryReservation.reserved_quantity,
            )
            .order_by(ProductionPlan.id, InventoryReservation.id)
        )
        plans: dict[int, dict] = {}
        for plan, order, reservation, stock, item in rows:
            item_name = item.item_name
            if item.item_type == "part" and item.product_bom_id is not None:
                bom_item = session.get(ProductBom, item.product_bom_id)
                if bom_item is not None:
                    item_name = bom_item.part_name
            entry = plans.setdefault(plan.id, {
                "production_plan_id": plan.id,
                "customer_order_id": order.id,
                "customer_order_no": order.customer_order_no,
                "department_code": department_code,
                "items": [],
            })
            entry["items"].append({
                "reservation_id": reservation.id,
                "item_code": item.item_code,
                "item_name": item_name,
                "reserved_quantity": reservation.reserved_quantity,
                "issued_quantity": reservation.issued_quantity,
                "remaining_quantity": reservation.reserved_quantity - reservation.issued_quantity,
                "completed_node_label": _completed_node_label(session, stock),
            })
        return list(plans.values())


def issue_outbound_plan(
    production_plan_id: int,
    department_code: str,
    quantities: dict[int, int],
    actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        issue_plan_reservations(
            session,
            production_plan_id=production_plan_id,
            department_code=department_code,
            quantities=quantities,
            actor_username=actor_username,
        )
    return next(
        (item for item in list_outbound_plans(department_code)
         if item["production_plan_id"] == production_plan_id),
        {
            "production_plan_id": production_plan_id,
            "customer_order_id": 0,
            "customer_order_no": "",
            "department_code": department_code,
            "items": [],
        },
    )


def _completed_node_label(session: Session, item: InventoryStock) -> str:
    from modules.production_core.flow import completed_node_display_label, load_product_flow
    flow, nodes = load_product_flow(session, item.product_id, item.product_version)
    return completed_node_display_label(
        flow,
        nodes,
        item.flow_node_id,
        item.completed_flow_node_id,
    )


def _serialize_stock(session: Session, item: InventoryStock) -> dict:
    return {
        "id": item.id,
        "department_code": item.department_code,
        "item_type": item.item_type,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "product_bom_id": item.product_bom_id,
        "flow_node_id": item.flow_node_id,
        "completed_flow_node_id": item.completed_flow_node_id,
        "completed_node_label": _completed_node_label(session, item),
        "item_code": item.item_code,
        "item_name": item.item_name,
        "quantity": item.quantity,
        "reserved_quantity": item.reserved_quantity,
        "available_quantity": item.quantity - item.reserved_quantity,
        "revision": item.revision,
    }


__all__ = [
    "issue_outbound_plan",
    "list_outbound_plans",
    "list_stocks",
    "list_transactions",
]
