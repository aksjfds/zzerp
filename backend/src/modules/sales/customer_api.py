"""Transaction-aware customer lookup and creation API."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.errors import DomainError
from modules.sales.persistence import Customer


@dataclass(frozen=True, slots=True)
class CustomerReference:
    id: int
    customer_name: str


def resolve_customer(
    session,
    customer_id: int | None,
    customer_name: str | None,
    *,
    allow_create: bool,
) -> CustomerReference:
    if customer_id is not None:
        customer = session.get(Customer, customer_id)
        if customer is None:
            raise DomainError(
                "customer_not_found",
                "所选客户不存在，请重新选择",
                path="customer_id",
            )
        return CustomerReference(
            id=customer.id,
            customer_name=customer.customer_name,
        )
    normalized_name = (customer_name or "").strip()
    if not allow_create or not normalized_name:
        raise DomainError(
            "customer_required",
            "请选择客户或输入新客户名称",
            path="customer_id",
        )
    customer = session.scalar(
        select(Customer)
        .where(Customer.customer_name == normalized_name)
        .with_for_update()
    )
    if customer is None:
        customer = Customer(customer_name=normalized_name)
        session.add(customer)
        session.flush()
    return CustomerReference(
        id=customer.id,
        customer_name=customer.customer_name,
    )


def customer_names_by_ids(
    session: Session,
    customer_ids: set[int],
) -> dict[int, str]:
    if not customer_ids:
        return {}
    return {
        customer_id: customer_name
        for customer_id, customer_name in session.execute(
            select(Customer.id, Customer.customer_name).where(
                Customer.id.in_(customer_ids)
            )
        )
    }


def customer_ids_matching_name(
    session: Session,
    keyword: str,
) -> frozenset[int]:
    normalized = keyword.strip()
    if not normalized:
        return frozenset()
    return frozenset(
        session.scalars(
            select(Customer.id).where(
                Customer.customer_name.ilike(f"%{normalized}%")
            )
        ).all()
    )


__all__ = [
    "CustomerReference",
    "customer_ids_matching_name",
    "customer_names_by_ids",
    "resolve_customer",
]
