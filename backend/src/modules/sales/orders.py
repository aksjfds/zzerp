from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, utc_now
from modules.sales.persistence import Customer
from modules.sales.persistence import CustomerOrder
from modules.sales.persistence import CustomerOrderItem
from modules.sales.order_support import (
    ensure_expected_revision,
    order_not_found,
    raise_order_integrity_error,
    replace_order_items,
    resolve_order_products,
    serialize_order,
)
from modules.sales.repository import CustomerOrderRepository
from modules.sales.context_api import (
    OrderPlanState,
    SalesEngineeringPort,
    SalesInventoryPort,
    SalesPlanningPort,
    SalesProductionPort,
)
from schemas.sales import CustomerOrderCreate, CustomerOrderUpdate
from modules.errors import DomainError


def _production_plan_started(plan: OrderPlanState | None) -> bool:
    return plan is not None and plan.confirmed_at is not None


def list_orders(
    page: int,
    page_size: int,
    *,
    statuses: set[str] | None = None,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = CustomerOrderRepository(session)
        orders = repository.list((page - 1) * page_size, page_size, statuses)
        product_ids = {item.product_id for order in orders for item in order.items}
        products = engineering.get_product_references(session, product_ids)
        plans_by_order_id = planning.order_plan_states(
            session,
            {order.id for order in orders},
        )
        return [
            serialize_order(
                session,
                item,
                products,
                production_plan_started=_production_plan_started(
                    plans_by_order_id.get(item.id)
                ),
                production_plan_status=(
                    plans_by_order_id[item.id].status
                    if item.id in plans_by_order_id
                    else None
                ),
            )
            for item in orders
        ], repository.count(statuses)


def list_order_progress_details(
    page: int,
    page_size: int,
    customer_id: int | None = None,
    *,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
    inventory: SalesInventoryPort,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        condition = CustomerOrder.customer_id == customer_id if customer_id is not None else True
        total = session.scalar(
            select(func.count(CustomerOrderItem.id))
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .where(condition)
        ) or 0
        statement = (
            select(CustomerOrderItem, CustomerOrder)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .where(condition)
            .order_by(CustomerOrder.created_at.desc(), CustomerOrder.id.desc(), CustomerOrderItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = session.execute(statement).all()
        order_item_ids = [item.id for item, _order in rows]
        products = engineering.get_product_references(
            session,
            {item.product_id for item, _order in rows},
        )
        planned_quantity_by_item = planning.planned_product_quantities(
            session,
            order_item_ids,
        )
        shipped_quantity_by_item = inventory.order_item_shipped_quantities(
            session,
            order_item_ids,
        )
        data = []
        for item, order in rows:
            product = products[item.product_id]
            shipped_quantity = min(
                int(shipped_quantity_by_item.get(item.id, 0)),
                item.quantity,
            )
            data.append({
                "customer_order_id": order.id,
                "customer_order_item_id": item.id,
                "factory_code": product.factory_code,
                "product_name": product.product_name,
                "order_date": order.created_at.astimezone(BUSINESS_TIMEZONE).date(),
                "customer_order_no": order.customer_order_no,
                "customer_code": product.customer_code,
                "order_quantity": item.quantity,
                "task_quantity": int(planned_quantity_by_item.get(item.id, 0)),
                "shipped_quantity": shipped_quantity,
                "outstanding_quantity": max(item.quantity - shipped_quantity, 0),
                "delivery_date": item.delivery_date,
                "remark": item.remark or order.remark or "",
            })
        return data, total


def get_order(
    order_id: int,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
) -> dict:
    with SessionLocal() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise order_not_found()
        plan = planning.order_plan_state(session, order.id)
        products = engineering.get_product_references(
            session,
            {item.product_id for item in order.items},
        )
        return serialize_order(
            session,
            order,
            products,
            production_plan_started=_production_plan_started(plan),
        )


def create_order(
    payload: CustomerOrderCreate,
    engineering: SalesEngineeringPort,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            customer = session.get(Customer, payload.customer_id)
            if customer is None:
                raise DomainError("customer_not_found", "所选客户不存在", path="customer_id")
            products = resolve_order_products(
                session,
                payload.items,
                customer.id,
                engineering,
            )
            order = CustomerOrder(
                customer_order_no=payload.customer_order_no,
                customer=customer,
                remark=payload.remark or None,
            )
            repository.add(order)
            replace_order_items(order, payload.items, products)
            session.flush()
            result = serialize_order(
                session,
                order,
                products,
            )
        return result
    except IntegrityError as exc:
        raise_order_integrity_error(exc)


def update_order(
    order_id: int,
    payload: CustomerOrderUpdate,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            order = repository.get_for_update(order_id)
            if order is None:
                raise order_not_found()
            plan = planning.order_plan_state(session, order.id, for_update=True)
            if order.status != "draft" and not (
                order.status == "cancelled" and not _production_plan_started(plan)
            ):
                raise DomainError(
                    "customer_order_not_editable",
                    "只有草稿订单或生产计划尚未确认的已取消订单允许修改",
                )
            ensure_expected_revision(order, payload.expected_revision)
            if plan is not None:
                planning.delete_order_plan(session, order.id)
            target_customer_id = payload.customer_id or order.customer_id
            customer = session.get(Customer, target_customer_id)
            if customer is None:
                raise DomainError("customer_not_found", "所选客户不存在", path="customer_id")
            products = resolve_order_products(
                session,
                payload.items,
                customer.id,
                engineering,
            )
            if payload.customer_order_no is not None:
                order.customer_order_no = payload.customer_order_no
            order.customer = customer
            order.remark = payload.remark or None
            order.updated_at = utc_now()
            order.status = "draft"
            order.revision += 1
            replace_order_items(order, payload.items, products)
            session.flush()
            return serialize_order(
                session,
                order,
                products,
            )
    except IntegrityError as exc:
        raise_order_integrity_error(exc)


def change_status(
    order_id: int,
    target: str,
    expected_revision: int,
    *,
    actor_username: str,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
    production: SalesProductionPort,
) -> dict:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise order_not_found()
        ensure_expected_revision(order, expected_revision)
        if target == "confirmed":
            if order.status != "draft":
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许确认")
            planning.rebuild_order_plan(session, order)
        elif target == "cancelled":
            if order.status not in {"draft", "confirmed", "planned"}:
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许取消")
            planning.cancel_order_plan(session, order, actor_username)
            production.cancel_order_production(session, order)
        else:
            raise DomainError("invalid_customer_order_status", "不支持的订单状态操作")
        order.status = target
        order.updated_at = utc_now()
        order.revision += 1
        session.flush()
        return serialize_order(
            session,
            order,
            engineering.get_product_references(
                session,
                {item.product_id for item in order.items},
            ),
            production_plan_started=_production_plan_started(
                planning.order_plan_state(session, order.id)
            ),
        )


def confirm_production_plan(
    order_id: int,
    expected_revision: int,
    plan_expected_revision: int,
    *,
    actor_username: str,
    planning: SalesPlanningPort,
    engineering: SalesEngineeringPort,
) -> dict:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise order_not_found()
        ensure_expected_revision(order, expected_revision)
        if order.status != "confirmed":
            raise DomainError(
                "production_plan_order_not_confirmed",
                "只有已确认客户订单的生产计划允许确认",
            )
        planning.confirm_order_plan(
            session,
            order,
            expected_revision=plan_expected_revision,
            actor_username=actor_username,
        )
        order.status = "planned"
        order.updated_at = utc_now()
        order.revision += 1
        session.flush()
        return serialize_order(
            session,
            order,
            engineering.get_product_references(
                session,
                {item.product_id for item in order.items},
            ),
        )


def delete_order(order_id: int, expected_revision: int) -> None:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise order_not_found()
        if order.status != "draft":
            raise DomainError("customer_order_not_deletable", "只有草稿订单允许删除")
        ensure_expected_revision(order, expected_revision)
        repository.delete(order)
