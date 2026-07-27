"""Immutable product identity projections for collaborating modules."""

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.process_flow import validate_process_flow
from modules.engineering.persistence import Product, ProductBom, ProductProcessFlow
from modules.errors import DomainError
from modules.organization.read_api import get_procedure_routes
from schemas.engineering import ProcessFlowPayload


@dataclass(frozen=True, slots=True)
class ProductReference:
    id: int
    customer_id: int
    product_name: str
    factory_code: str
    version: int


def _product_reference(product: Product) -> ProductReference:
    return ProductReference(
        id=product.id,
        customer_id=product.customer_id,
        product_name=product.product_name,
        factory_code=product.factory_code,
        version=product.version,
    )


def get_product_reference(
    session: Session,
    product_id: int,
) -> ProductReference | None:
    product = session.get(Product, product_id)
    if product is None:
        return None
    return _product_reference(product)


def get_product_references(
    session: Session,
    product_ids: Collection[int],
) -> dict[int, ProductReference]:
    if not product_ids:
        return {}
    return {
        product.id: _product_reference(product)
        for product in session.scalars(
            select(Product).where(Product.id.in_(product_ids))
        )
    }


def resolve_order_product_references(
    session: Session,
    product_ids: Collection[int],
    customer_id: int,
) -> dict[int, ProductReference]:
    ids = set(product_ids)
    if not ids:
        return {}
    products = {
        product.id: product
        for product in session.scalars(
            select(Product)
            .where(Product.id.in_(ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    if len(products) != len(ids):
        raise DomainError(
            "invalid_order_product",
            "订单包含不存在的产品",
            path="items",
        )
    for product in products.values():
        if product.customer_id != customer_id:
            raise DomainError(
                "order_product_customer_mismatch",
                "订单产品必须属于所选客户",
                path="items",
            )
        _validate_order_engineering_data(session, product)
    return {
        product_id: _product_reference(product)
        for product_id, product in products.items()
    }


def _validate_order_engineering_data(
    session: Session,
    product: Product,
) -> None:
    bom_ids = set(
        session.scalars(
            select(ProductBom.id).where(
                ProductBom.product_id == product.id,
                ProductBom.product_version == product.version,
            )
        ).all()
    )
    flow = session.scalar(
        select(ProductProcessFlow.flow_json).where(
            ProductProcessFlow.product_id == product.id,
            ProductProcessFlow.product_version == product.version,
        )
    )
    if not bom_ids or not flow or not flow.get("nodes"):
        raise DomainError(
            "product_engineering_data_missing",
            f"产品 {product.factory_code} 缺少当前版本 BOM 或流程图",
            path="items",
        )
    validated = ProcessFlowPayload.model_validate(flow)
    validate_process_flow(validated, bom_ids)
    procedure_ids = {
        node.procedure_id
        for node in validated.nodes
        if node.type == "process"
    }
    if set(get_procedure_routes(session, procedure_ids)) != procedure_ids:
        raise DomainError(
            "process_procedure_invalid",
            f"产品 {product.factory_code} 的流程包含失效工艺",
            path="items",
        )


__all__ = [
    "ProductReference",
    "get_product_reference",
    "get_product_references",
    "resolve_order_product_references",
]
