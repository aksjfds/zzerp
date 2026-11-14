"""Immutable product identity projections for collaborating modules."""

from collections.abc import Collection

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import ProductReference
from zzerp.modules.engineering.persistence import Product, ProductAppearance


def _product_reference(product: Product) -> ProductReference:
    return ProductReference(
        id=product.id,
        customer_id=product.customer_id,
        product_name=product.product_name,
        factory_code=product.factory_code,
        customer_code=product.customer_code,
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
        for product in session.scalars(select(Product).where(Product.id.in_(product_ids)))
    }


def resolve_plan_product(
    session: Session,
    product_id: int,
    customer_id: int,
) -> ProductReference:
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise DomainError("product_not_found", "所选产品不存在", path="product_id", status_code=404)
    if product.customer_id != customer_id:
        raise DomainError(
            "plan_product_customer_mismatch",
            "所选产品必须属于所选客户",
            path="product_id",
        )
    return _product_reference(product)


def matching_product_ids_query(keyword: str) -> Select[tuple[int]]:
    pattern = f"%{keyword.strip()}%"
    return select(Product.id).where(
        Product.factory_code.ilike(pattern) | Product.product_name.ilike(pattern),
    )


def appearance_names(session: Session, appearance_ids: Collection[int]) -> dict[int, str]:
    if not appearance_ids:
        return {}
    return dict(
        session.execute(
            select(ProductAppearance.id, ProductAppearance.appearance_name).where(
                ProductAppearance.id.in_(appearance_ids)
            )
        ).all()
    )


def ensure_plan_appearance(session: Session, product_id: int, appearance_id: int) -> None:
    if (
        session.scalar(
            select(ProductAppearance.id).where(
                ProductAppearance.product_id == product_id, ProductAppearance.id == appearance_id
            )
        )
        is None
    ):
        raise DomainError(
            "appearance_not_found", "外观不属于所选产品", path="appearance_id", status_code=404
        )
