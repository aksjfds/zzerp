"""Immutable engineering projections used by piece-rate configuration."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.engineering.persistence import (
    Product,
    ProductBom,
    ProductProcessFlow,
    ProductVersion,
)


@dataclass(frozen=True, slots=True)
class PricingBomView:
    id: int
    part_name: str
    part_no: str


@dataclass(frozen=True, slots=True)
class ProductPricingView:
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    updated_at: datetime
    flow_json: dict | None
    boms: tuple[PricingBomView, ...]


def _bom_views(
    session: Session,
    product_versions: Collection[tuple[int, int]],
) -> dict[tuple[int, int], list[PricingBomView]]:
    if not product_versions:
        return {}
    product_ids = {product_id for product_id, _ in product_versions}
    rows = session.scalars(
        select(ProductBom)
        .where(ProductBom.product_id.in_(product_ids))
        .order_by(ProductBom.product_id, ProductBom.sort_order)
    )
    result: dict[tuple[int, int], list[PricingBomView]] = {}
    for bom in rows:
        key = (bom.product_id, bom.product_version)
        if key in product_versions:
            result.setdefault(key, []).append(
                PricingBomView(
                    id=bom.id,
                    part_name=bom.part_name,
                    part_no=bom.part_no,
                )
            )
    return result


def get_product_pricing_view(
    session: Session,
    product_id: int,
    product_version: int,
) -> ProductPricingView | None:
    exists = session.get(ProductVersion, (product_id, product_version))
    product = session.get(Product, product_id)
    if exists is None or product is None:
        return None
    flow_json = session.scalar(
        select(ProductProcessFlow.flow_json).where(
            ProductProcessFlow.product_id == product_id,
            ProductProcessFlow.product_version == product_version,
        )
    )
    boms = _bom_views(session, {(product_id, product_version)})
    return ProductPricingView(
        product_id=product.id,
        product_version=product_version,
        product_name=product.product_name,
        factory_code=product.factory_code,
        updated_at=product.updated_at,
        flow_json=flow_json,
        boms=tuple(boms.get((product_id, product_version), ())),
    )


__all__ = [
    "PricingBomView",
    "ProductPricingView",
    "get_product_pricing_view",
]
