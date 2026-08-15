from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, utc_now
from modules.engineering.product_reference_api import get_product_references
from modules.engineering.model_api import Product
from modules.sales.persistence import Customer
from modules.sales.persistence import CustomerOrder
from modules.sales.persistence import CustomerOrderItem
from modules.planning.api import (
    cancel_order_plan,
    confirm_order_plan,
    rebuild_order_plan,
)
from modules.planning.model_api import ProductionPlan, ProductionPlanItem
from modules.planning.plan_builder import planned_product_quantity
from modules.sales.order_support import (
    ensure_expected_revision,
    order_not_found,
    raise_order_integrity_error,
    replace_order_items,
    resolve_order_products,
    serialize_order,
)
from modules.sales.repository import CustomerOrderRepository
from schemas.sales import CustomerOrderCreate, CustomerOrderUpdate
from modules.errors import DomainError
from modules.production_core.persistence import ProductionItem, ProductionMovement
from modules.production_core.operational_api import load_product_flow, terminal_unit_quantity


def _order_plan(session, order_id: int, *, for_update: bool = False):
    statement = select(ProductionPlan).where(
        ProductionPlan.customer_order_id == order_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _production_plan_started(plan: ProductionPlan | None) -> bool:
    return plan is not None and plan.confirmed_at is not None


def list_orders(
    page: int,
    page_size: int,
    *,
    include_progress: bool = False,
    statuses: set[str] | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = CustomerOrderRepository(session)
        orders = repository.list((page - 1) * page_size, page_size, statuses)
        product_ids = {item.product_id for order in orders for item in order.items}
        products = get_product_references(session, product_ids)
        plans_by_order_id = {
            plan.customer_order_id: plan
            for plan in session.scalars(
                select(ProductionPlan).where(
                ProductionPlan.customer_order_id.in_([order.id for order in orders])
            )
            )
        } if orders else {}
        return [
            serialize_order(
                session,
                item,
                products,
                include_progress=include_progress,
                production_plan_started=_production_plan_started(
                    plans_by_order_id.get(item.id)
                ),
            )
            for item in orders
        ], repository.count(statuses)


def list_order_progress_details(
    page: int,
    page_size: int,
    customer_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        condition = CustomerOrder.customer_id == customer_id if customer_id is not None else True
        total = session.scalar(
            select(func.count(CustomerOrderItem.id))
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .where(condition)
        ) or 0
        statement = (
            select(CustomerOrderItem, CustomerOrder, Product)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .join(Product, Product.id == CustomerOrderItem.product_id)
            .where(condition)
            .order_by(CustomerOrder.created_at.desc(), CustomerOrder.id.desc(), CustomerOrderItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = session.execute(statement).all()
        order_item_ids = [item.id for item, _order, _product in rows]
        plan_items_by_order_item: dict[int, list[ProductionPlanItem]] = {}
        if order_item_ids:
            for plan_item in session.scalars(
                select(ProductionPlanItem).where(
                    ProductionPlanItem.customer_order_item_id.in_(order_item_ids)
                )
            ):
                plan_items_by_order_item.setdefault(
                    plan_item.customer_order_item_id,
                    [],
                ).append(plan_item)
        planned_quantity_by_item = {
            order_item_id: planned_product_quantity(plan_items)
            for order_item_id, plan_items in plan_items_by_order_item.items()
        }
        shipped_raw_by_item = {
            order_item_id: shipped_raw
            for order_item_id, shipped_raw in session.execute(
                select(
                    ProductionItem.customer_order_item_id,
                    func.coalesce(func.sum(ProductionMovement.quantity), 0),
                )
                .join(
                    ProductionMovement,
                    ProductionMovement.production_item_id == ProductionItem.id,
                )
                .where(
                    ProductionItem.customer_order_item_id.in_(order_item_ids),
                    ProductionMovement.movement_type == "customer_shipment",
                )
                .group_by(ProductionItem.customer_order_item_id)
            )
        } if order_item_ids else {}
        data = []
        for item, order, product in rows:
            shipped_raw = int(shipped_raw_by_item.get(item.id, 0))
            unit_quantity = 1
            try:
                flow, nodes = load_product_flow(session, item.product_id, item.product_version)
                shipping = next(
                    (node for node in nodes.values() if node.get("type") == "shipping"),
                    None,
                )
                if shipping is not None:
                    unit_quantity = terminal_unit_quantity(
                        session,
                        flow,
                        nodes,
                        shipping["id"],
                    ) or 1
            except DomainError:
                pass
            shipped_quantity = min(shipped_raw // unit_quantity, item.quantity)
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


def get_order(order_id: int) -> dict:
    with SessionLocal() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise order_not_found()
        plan = _order_plan(session, order.id)
        return serialize_order(
            session,
            order,
            production_plan_started=_production_plan_started(plan),
        )


def create_order(payload: CustomerOrderCreate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            customer = session.get(Customer, payload.customer_id)
            if customer is None:
                raise DomainError("customer_not_found", "所选客户不存在", path="customer_id")
            products = resolve_order_products(session, payload.items, customer.id)
            order = CustomerOrder(
                customer_order_no=payload.customer_order_no,
                customer=customer,
                remark=payload.remark or None,
            )
            repository.add(order)
            replace_order_items(order, payload.items, products)
            session.flush()
            result = serialize_order(session, order)
        return result
    except IntegrityError as exc:
        raise_order_integrity_error(exc)


def update_order(order_id: int, payload: CustomerOrderUpdate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            order = repository.get_for_update(order_id)
            if order is None:
                raise order_not_found()
            plan = _order_plan(session, order.id, for_update=True)
            if order.status != "draft" and not (
                order.status == "cancelled" and not _production_plan_started(plan)
            ):
                raise DomainError(
                    "customer_order_not_editable",
                    "只有草稿订单或生产计划尚未确认的已取消订单允许修改",
                )
            ensure_expected_revision(order, payload.expected_revision)
            if plan is not None:
                session.delete(plan)
                session.flush()
            target_customer_id = payload.customer_id or order.customer_id
            customer = session.get(Customer, target_customer_id)
            if customer is None:
                raise DomainError("customer_not_found", "所选客户不存在", path="customer_id")
            products = resolve_order_products(session, payload.items, customer.id)
            if payload.customer_order_no is not None:
                order.customer_order_no = payload.customer_order_no
            order.customer = customer
            order.remark = payload.remark or None
            order.updated_at = utc_now()
            order.status = "draft"
            order.revision += 1
            replace_order_items(order, payload.items, products)
            session.flush()
            return serialize_order(session, order)
    except IntegrityError as exc:
        raise_order_integrity_error(exc)


def change_status(
    order_id: int,
    target: str,
    expected_revision: int,
    *,
    actor_username: str,
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
            rebuild_order_plan(session, order)
        elif target == "cancelled":
            if order.status not in {"draft", "confirmed", "planned"}:
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许取消")
            cancel_order_plan(session, order, actor_username)
        else:
            raise DomainError("invalid_customer_order_status", "不支持的订单状态操作")
        order.status = target
        order.updated_at = utc_now()
        order.revision += 1
        session.flush()
        return serialize_order(
            session,
            order,
            production_plan_started=_production_plan_started(
                _order_plan(session, order.id)
            ),
        )


def confirm_production_plan(
    order_id: int,
    expected_revision: int,
    plan_expected_revision: int,
    *,
    actor_username: str,
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
        confirm_order_plan(
            session,
            order,
            expected_revision=plan_expected_revision,
            actor_username=actor_username,
        )
        order.status = "planned"
        order.updated_at = utc_now()
        order.revision += 1
        session.flush()
        return serialize_order(session, order)


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
