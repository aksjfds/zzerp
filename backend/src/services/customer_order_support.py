from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from domain.time import business_iso
from domain.process_flow import validate_process_flow
from models.engineering import Product, ProductBom
from models.organization import Procedure
from models.sales import CustomerOrder, CustomerOrderItem
from schemas.engineering import ProcessFlowPayload
from schemas.sales import CustomerOrderItemInput
from services.errors import DomainError
from services.production_flow import load_product_flow


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
    products: dict[int, Product] | None = None,
) -> dict:
    if products is None:
        product_ids = {item.product_id for item in order.items}
        products = {
            item.id: item
            for item in session.scalars(
                select(Product).where(Product.id.in_(product_ids))
            ).all()
        }
    return {
        "id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "status": order.status,
        "revision": order.revision,
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
        "created_at": business_iso(order.created_at),
        "updated_at": business_iso(order.updated_at),
    }


def resolve_order_products(
    session,
    items: list[CustomerOrderItemInput],
) -> dict[int, Product]:
    product_ids = {item.product_id for item in items}
    products = {
        item.id: item
        for item in session.scalars(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        ).all()
    }
    if len(products) != len(product_ids):
        raise DomainError("invalid_order_product", "订单包含不存在的产品", path="items")
    for product in products.values():
        _validate_product_engineering_data(session, product)
    return products


def replace_order_items(
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


def raise_order_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(
        getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
    )
    if "customer_order_no" in constraint:
        raise DomainError(
            "customer_order_no_conflict", "客户订单编号已存在", status_code=409
        ) from exc
    raise DomainError(
        "customer_order_data_conflict",
        "客户订单数据违反关联或数量约束",
        status_code=409,
    ) from exc


def _validate_product_engineering_data(session, product: Product) -> None:
    bom_ids = set(
        session.scalars(
            select(ProductBom.id).where(
                ProductBom.product_id == product.id,
                ProductBom.product_version == product.version,
            )
        ).all()
    )
    try:
        flow, _ = load_product_flow(session, product.id, product.version)
    except DomainError:
        flow = None
    if not bom_ids or flow is None or not flow.get("nodes"):
        raise DomainError(
            "product_engineering_data_missing",
            f"产品 {product.factory_code} 缺少当前版本 BOM 或流程图",
            path="items",
        )
    validated = ProcessFlowPayload.model_validate(flow)
    validate_process_flow(validated, bom_ids)
    procedure_ids = {
        node.procedure_id for node in validated.nodes if node.type == "process"
    }
    existing_procedure_ids = set(
        session.scalars(
            select(Procedure.id).where(Procedure.id.in_(procedure_ids))
        ).all()
    )
    if existing_procedure_ids != procedure_ids:
        raise DomainError(
            "process_procedure_invalid",
            f"产品 {product.factory_code} 的流程包含失效工艺",
            path="items",
        )
