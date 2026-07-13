from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.engineering import Product
from models.sales import CustomerOrder
from repositories.customer_orders import CustomerOrderRepository
from schemas.sales import CustomerOrderCreate, CustomerOrderUpdate
from services.customer_order_support import (
    ensure_expected_revision,
    order_not_found,
    raise_order_integrity_error,
    replace_order_items,
    resolve_order_products,
    serialize_order,
)
from services.errors import DomainError
from services.production_order_lifecycle import cancel_order_production, initialize_order_production


def list_orders(page: int, page_size: int) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = CustomerOrderRepository(session)
        orders = repository.list((page - 1) * page_size, page_size)
        product_ids = {item.product_id for order in orders for item in order.items}
        products = {
            item.id: item
            for item in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        }
        return [serialize_order(session, item, products) for item in orders], repository.count()


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
            products = resolve_order_products(session, payload.items)
            order = CustomerOrder(
                customer_order_no=payload.customer_order_no,
                customer_name=payload.customer_name,
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
            products = resolve_order_products(session, payload.items)
            if payload.customer_order_no is not None:
                order.customer_order_no = payload.customer_order_no
            if payload.customer_name is not None:
                order.customer_name = payload.customer_name
            order.remark = payload.remark or None
            order.updated_at = datetime.now()
            order.revision += 1
            replace_order_items(order, payload.items, products)
            session.flush()
            return serialize_order(session, order)
    except IntegrityError as exc:
        raise_order_integrity_error(exc)


def change_status(order_id: int, target: str, expected_revision: int) -> dict:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise order_not_found()
        ensure_expected_revision(order, expected_revision)
        if target == "confirmed":
            if order.status != "draft":
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许确认")
            initialize_order_production(session, order)
        elif target == "cancelled":
            if order.status not in {"draft", "confirmed", "planned"}:
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许取消")
            if order.status != "draft":
                cancel_order_production(session, order)
        else:
            raise DomainError("invalid_customer_order_status", "不支持的订单状态操作")
        order.status = target
        order.updated_at = datetime.now()
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
