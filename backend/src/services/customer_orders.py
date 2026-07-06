from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow
from models.sales import CustomerOrder, CustomerOrderItem
from repositories.customer_orders import CustomerOrderRepository
from schemas.sales import CustomerOrderCreate, CustomerOrderItemInput, CustomerOrderUpdate
from services.errors import DomainError


def _not_found() -> DomainError:
    return DomainError("customer_order_not_found", "客户订单不存在", status_code=404)


def _serialize(session, order: CustomerOrder) -> dict:
    product_ids = {item.product_id for item in order.items}
    products = {
        item.id: item
        for item in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    }
    return {
        "id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "status": order.status,
        "remark": order.remark or "",
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_version": item.product_version,
                "product_name": products[item.product_id].product_name,
                "factory_code": products[item.product_id].factory_code,
                "quantity": item.quantity,
                "delivery_date": item.delivery_date,
                "remark": item.remark or "",
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat(timespec="minutes"),
        "updated_at": order.updated_at.isoformat(timespec="minutes"),
    }


def _resolve_products(session, items: list[CustomerOrderItemInput]) -> dict[int, Product]:
    product_ids = {item.product_id for item in items}
    products = {
        item.id: item
        for item in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    }
    if len(products) != len(product_ids):
        raise DomainError("invalid_order_product", "订单包含不存在的产品", path="items")
    for product in products.values():
        has_bom = session.scalar(
            select(ProductBom.id).where(
                ProductBom.product_id == product.id,
                ProductBom.product_version == product.version,
            ).limit(1)
        )
        has_flow = session.scalar(
            select(ProductProcessFlow.id).where(
                ProductProcessFlow.product_id == product.id,
                ProductProcessFlow.product_version == product.version,
            ).limit(1)
        )
        if not has_bom or not has_flow:
            raise DomainError(
                "product_engineering_data_missing",
                f"产品 {product.factory_code} 缺少当前版本 BOM 或流程图",
                path="items",
            )
    return products


def _replace_items(
    order: CustomerOrder,
    items: list[CustomerOrderItemInput],
    products: dict[int, Product],
) -> None:
    order.items.clear()
    for item in items:
        product = products[item.product_id]
        order.items.append(
            CustomerOrderItem(
                product_id=product.id,
                product_version=product.version,
                quantity=item.quantity,
                delivery_date=item.delivery_date,
                remark=item.remark or None,
            )
        )


def list_orders() -> list[dict]:
    with SessionLocal() as session:
        return [_serialize(session, item) for item in CustomerOrderRepository(session).list()]


def get_order(order_id: int) -> dict:
    with SessionLocal() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise _not_found()
        return _serialize(session, order)


def create_order(payload: CustomerOrderCreate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            products = _resolve_products(session, payload.items)
            order = CustomerOrder(
                customer_order_no=payload.customer_order_no,
                customer_name=payload.customer_name,
                remark=payload.remark or None,
            )
            repository.add(order)
            _replace_items(order, payload.items, products)
            session.flush()
            result = _serialize(session, order)
        return result
    except IntegrityError as exc:
        raise DomainError(
            "customer_order_no_conflict", "客户订单编号已存在", status_code=409
        ) from exc


def update_order(order_id: int, payload: CustomerOrderUpdate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            order = repository.get(order_id)
            if order is None:
                raise _not_found()
            if order.status != "draft":
                raise DomainError("customer_order_not_editable", "只有草稿订单允许修改")
            products = _resolve_products(session, payload.items)
            if payload.customer_order_no is not None:
                order.customer_order_no = payload.customer_order_no
            if payload.customer_name is not None:
                order.customer_name = payload.customer_name
            order.remark = payload.remark or None
            order.updated_at = datetime.now()
            _replace_items(order, payload.items, products)
            session.flush()
            return _serialize(session, order)
    except IntegrityError as exc:
        raise DomainError(
            "customer_order_no_conflict", "客户订单编号已存在", status_code=409
        ) from exc


def change_status(order_id: int, target: str) -> dict:
    with SessionLocal.begin() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise _not_found()
        if order.status != "draft":
            raise DomainError("invalid_customer_order_status", "当前订单状态不允许该操作")
        if target == "confirmed":
            from services.production_repositories import provision_order_repositories

            provision_order_repositories(session, order)
        order.status = target
        order.updated_at = datetime.now()
        session.flush()
        return _serialize(session, order)


def delete_order(order_id: int) -> None:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get(order_id)
        if order is None:
            raise _not_found()
        if order.status != "draft":
            raise DomainError("customer_order_not_deletable", "只有草稿订单允许删除")
        repository.delete(order)
