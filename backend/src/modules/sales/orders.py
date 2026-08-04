from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from domain.time import utc_now
from modules.engineering.product_reference_api import get_product_references
from modules.sales.persistence import Customer
from modules.sales.persistence import CustomerOrder
from modules.planning.api import (
    cancel_order_plan,
    confirm_order_plan,
    rebuild_order_plan,
)
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
        return [
            serialize_order(
                session,
                item,
                products,
                include_progress=include_progress,
            )
            for item in orders
        ], repository.count(statuses)


def get_order(order_id: int) -> dict:
    with SessionLocal() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise order_not_found()
        return serialize_order(session, order)


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
            if order.status != "draft":
                raise DomainError("customer_order_not_editable", "只有草稿订单允许修改")
            ensure_expected_revision(order, payload.expected_revision)
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
        return serialize_order(session, order)


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
