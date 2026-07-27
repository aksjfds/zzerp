"""Read-only reference checks owned by the sales module."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.sales.persistence import CustomerOrderItem


def has_product_reference(session: Session, product_id: int) -> bool:
    return bool(
        session.scalar(
            select(CustomerOrderItem.id)
            .where(CustomerOrderItem.product_id == product_id)
            .limit(1)
        )
    )


def has_product_version_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return bool(
        session.scalar(
            select(CustomerOrderItem.id)
            .where(
                CustomerOrderItem.product_id == product_id,
                CustomerOrderItem.product_version == product_version,
            )
            .limit(1)
        )
    )


__all__ = ["has_product_reference", "has_product_version_reference"]
