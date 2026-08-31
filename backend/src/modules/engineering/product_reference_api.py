"""Immutable product identity projections for collaborating modules."""

from collections.abc import Collection
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from domain.errors import DomainViolation
from domain.product import ProductReference
from domain.process_flow import validate_process_flow
from modules.engineering.persistence import Product, ProductBom, ProductProcessFlow
from modules.engineering.support import packaging_workshop_ids
from modules.errors import DomainError
from modules.organization.read_api import get_workshop_routes
from schemas.engineering import ProcessFlowPayload


@dataclass(frozen=True, slots=True)
class ProductOrderReadiness:
    ready: bool
    reason: str


def _product_reference(product: Product) -> ProductReference:
    return ProductReference(
        id=product.id,
        customer_id=product.customer_id,
        product_name=product.product_name,
        factory_code=product.factory_code,
        customer_code=product.customer_code,
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
    readiness = get_product_order_readinesses(session, products.values())
    for product in products.values():
        status = readiness[product.id]
        if not status.ready:
            raise DomainError(
                "product_engineering_data_missing",
                f"产品 {product.factory_code} 不可用",
                path="items",
            )
    return {
        product_id: _product_reference(product)
        for product_id, product in products.items()
    }


def get_product_order_readinesses(
    session: Session,
    products: Collection[Product],
) -> dict[int, ProductOrderReadiness]:
    product_list = list(products)
    if not product_list:
        return {}
    version_keys = {(product.id, product.version) for product in product_list}
    bom_ids: dict[tuple[int, int], set[int]] = {key: set() for key in version_keys}
    for product_id, product_version, bom_id in session.execute(
        select(ProductBom.product_id, ProductBom.product_version, ProductBom.id).where(
            tuple_(ProductBom.product_id, ProductBom.product_version).in_(list(version_keys))
        )
    ):
        bom_ids[(product_id, product_version)].add(bom_id)
    flows = {
        (product_id, product_version): flow_json
        for product_id, product_version, flow_json in session.execute(
            select(
                ProductProcessFlow.product_id,
                ProductProcessFlow.product_version,
                ProductProcessFlow.flow_json,
            ).where(
                tuple_(
                    ProductProcessFlow.product_id,
                    ProductProcessFlow.product_version,
                ).in_(list(version_keys))
            )
        )
    }
    validated_flows: dict[int, ProcessFlowPayload] = {}
    result: dict[int, ProductOrderReadiness] = {}
    workshop_ids: set[int] = set()
    for product in product_list:
        key = (product.id, product.version)
        current_bom_ids = bom_ids[key]
        flow = flows.get(key)
        if not current_bom_ids:
            result[product.id] = ProductOrderReadiness(False, "当前版本缺少 BOM")
            continue
        if not flow or not flow.get("nodes"):
            result[product.id] = ProductOrderReadiness(False, "当前版本缺少正式流程图")
            continue
        try:
            validated = ProcessFlowPayload.model_validate(flow)
        except ValidationError:
            result[product.id] = ProductOrderReadiness(False, "当前版本正式流程图不完整")
            continue
        validated_flows[product.id] = validated
        workshop_ids.update(
            node.workshop_id
            for node in validated.nodes
            if node.type in {"process", "assembly"}
        )
    workshops = get_workshop_routes(session, workshop_ids)
    direct_inbound_workshop_ids = packaging_workshop_ids(workshops)
    for product in product_list:
        validated = validated_flows.get(product.id)
        if validated is None:
            continue
        flow_workshop_ids = {
            node.workshop_id
            for node in validated.nodes
            if node.type in {"process", "assembly"}
        }
        if not flow_workshop_ids.issubset(workshops):
            result[product.id] = ProductOrderReadiness(False, "流程图包含已失效车间")
            continue
        try:
            validate_process_flow(
                validated,
                bom_ids[(product.id, product.version)],
                direct_inbound_workshop_ids,
            )
        except DomainViolation:
            result[product.id] = ProductOrderReadiness(False, "当前版本正式流程图不完整")
            continue
        result[product.id] = ProductOrderReadiness(True, "")
    return result


__all__ = [
    "ProductReference",
    "ProductOrderReadiness",
    "get_product_order_readinesses",
    "get_product_reference",
    "get_product_references",
    "resolve_order_product_references",
]
