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
from modules.errors import DomainError
from schemas.engineering import ProcessFlowPayload


@dataclass(frozen=True, slots=True)
class ProductDesignReadiness:
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


def resolve_plan_product(
    session: Session, product_id: int, customer_id: int,
) -> ProductReference:
    product = session.scalar(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    if product is None:
        raise DomainError("product_not_found", "所选产品不存在", path="product_id", status_code=404)
    if product.customer_id != customer_id:
        raise DomainError(
            "plan_product_customer_mismatch", "所选产品必须属于所选客户",
            path="product_id",
        )
    return _product_reference(product)


def get_product_design_readinesses(
    session: Session,
    products: Collection[Product],
) -> dict[int, ProductDesignReadiness]:
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
    result: dict[int, ProductDesignReadiness] = {}
    for product in product_list:
        key = (product.id, product.version)
        if not bom_ids[key]:
            result[product.id] = ProductDesignReadiness(False, "当前版本缺少 BOM")
            continue
        flow = flows.get(key)
        if not flow or not flow.get("nodes"):
            result[product.id] = ProductDesignReadiness(False, "当前版本缺少正式流程图")
            continue
        try:
            validate_process_flow(ProcessFlowPayload.model_validate(flow))
        except (ValidationError, DomainViolation):
            result[product.id] = ProductDesignReadiness(False, "当前版本正式流程图不完整")
            continue
        result[product.id] = ProductDesignReadiness(True, "")
    return result


__all__ = [
    "ProductReference",
    "ProductDesignReadiness",
    "get_product_design_readinesses",
    "get_product_reference",
    "get_product_references",
    "resolve_plan_product",
    "matching_product_ids",
]


def matching_product_ids(session, keyword: str) -> set[int]:
    pattern = f"%{keyword.strip()}%"
    return set(session.scalars(select(Product.id).where(
        Product.factory_code.ilike(pattern) | Product.product_name.ilike(pattern),
    )))
