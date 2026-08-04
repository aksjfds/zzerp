from sqlalchemy.exc import IntegrityError

from domain.time import business_iso
from modules.engineering.product_reference_api import (
    ProductReference,
    get_product_references,
    resolve_order_product_references,
)
from modules.sales.persistence import CustomerOrder, CustomerOrderItem
from schemas.sales import CustomerOrderItemInput
from modules.errors import DomainError
from modules.production_core.sales_api import order_item_progress


def order_not_found() -> DomainError:
    return DomainError("customer_order_not_found", "客户订单不存在", status_code=404)


def ensure_expected_revision(order: CustomerOrder, expected_revision: int) -> None:
    if order.revision != expected_revision:
        raise DomainError(
            "customer_order_revision_conflict",
            "客户订单已被其他用户更新，请重新加载",
            status_code=409,
        )


def serialize_order(
    session,
    order: CustomerOrder,
    products: dict[int, ProductReference] | None = None,
    *,
    include_progress: bool = False,
) -> dict:
    if products is None:
        product_ids = {item.product_id for item in order.items}
        products = get_product_references(session, product_ids)
    item_rows = [
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
    ]
    progress_rows = []
    if include_progress:
        for item in order.items:
            progress = order_item_progress(
                session,
                item,
                order_status=order.status,
            )
            progress["product_name"] = products[item.product_id].product_name
            progress["factory_code"] = products[item.product_id].factory_code
            progress_rows.append(progress)
    return {
        "id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_id": order.customer_id,
        "customer_name": order.customer.customer_name,
        "status": order.status,
        "revision": order.revision,
        "remark": order.remark or "",
        "items": item_rows,
        "product_progress": progress_rows,
        "created_at": business_iso(order.created_at),
        "updated_at": business_iso(order.updated_at),
    }


def resolve_order_products(
    session,
    items: list[CustomerOrderItemInput],
    customer_id: int,
) -> dict[int, ProductReference]:
    if len({item.product_id for item in items}) != len(items):
        raise DomainError(
            "duplicate_order_product_version",
            "同一客户订单不能重复选择相同产品版本",
            path="items",
        )
    product_ids = {item.product_id for item in items}
    return resolve_order_product_references(
        session,
        product_ids,
        customer_id,
    )


def replace_order_items(
    order: CustomerOrder,
    items: list[CustomerOrderItemInput],
    products: dict[int, ProductReference],
) -> None:
    existing_items = list(order.items)
    existing_by_id = {item.id: item for item in existing_items}
    existing_by_product_version = {
        (item.product_id, item.product_version): item
        for item in existing_items
    }
    retained_ids: set[int] = set()
    next_items: list[CustomerOrderItem] = []
    for item in items:
        product = products[item.product_id]
        existing = existing_by_product_version.get((product.id, product.version))
        if existing is not None and existing.id in retained_ids:
            existing = None
        if existing is None and item.id is not None:
            existing = existing_by_id.get(item.id)
            if existing is None or existing.id in retained_ids:
                raise DomainError(
                    "customer_order_item_mismatch",
                    "订单明细已发生变化，请重新加载",
                    status_code=409,
                    path="items",
                )
        if existing is None:
            existing = CustomerOrderItem(
                product_id=product.id,
                product_version=product.version,
                quantity=item.quantity,
                delivery_date=item.delivery_date,
                remark=item.remark or None,
            )
        else:
            retained_ids.add(existing.id)
            existing.product_id = product.id
            existing.product_version = product.version
            existing.quantity = item.quantity
            existing.delivery_date = item.delivery_date
            existing.remark = item.remark or None
        next_items.append(existing)
    order.items[:] = next_items


def raise_order_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(
        getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
    )
    if "customer_order_no" in constraint:
        raise DomainError(
            "customer_order_no_conflict", "客户订单编号已存在", status_code=409
        ) from exc
    if constraint == "uq_customer_order_item_product_version":
        raise DomainError(
            "duplicate_order_product_version",
            "同一客户订单不能重复选择相同产品版本",
            status_code=409,
            path="items",
        ) from exc
    raise DomainError(
        "customer_order_data_conflict",
        "客户订单数据违反关联或数量约束",
        status_code=409,
    ) from exc
