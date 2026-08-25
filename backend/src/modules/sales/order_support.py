from sqlalchemy.exc import IntegrityError

from domain.product import ProductReference
from domain.time import business_iso
from modules.sales.context_api import SalesEngineeringPort, SalesProductionPort
from modules.sales.persistence import CustomerOrder, CustomerOrderItem
from schemas.sales import CustomerOrderItemInput
from modules.errors import DomainError


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
    production: SalesProductionPort,
    production_plan_started: bool = False,
    production_plan_status: str | None = None,
) -> dict:
    if products is None:
        raise DomainError("product_context_missing", "订单产品资料不完整")
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
    return {
        "id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_id": order.customer_id,
        "customer_name": order.customer.customer_name,
        "status": order.status,
        "production_plan_status": production_plan_status,
        "can_edit": order.status == "draft" or (
            order.status == "cancelled" and not production_plan_started
        ),
        "revision": order.revision,
        "remark": order.remark or "",
        "items": item_rows,
        "created_at": business_iso(order.created_at),
        "updated_at": business_iso(order.updated_at),
    }


def resolve_order_products(
    session,
    items: list[CustomerOrderItemInput],
    customer_id: int,
    engineering: SalesEngineeringPort,
) -> dict[int, ProductReference]:
    if len({item.product_id for item in items}) != len(items):
        raise DomainError(
            "duplicate_order_product_version",
            "同一客户订单不能重复选择相同产品版本",
            path="items",
        )
    product_ids = {item.product_id for item in items}
    return engineering.resolve_order_product_references(
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
