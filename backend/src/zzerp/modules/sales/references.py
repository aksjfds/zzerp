"""Transaction-aware customer lookup and creation API."""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.sales.contracts import CustomerReference
from zzerp.modules.sales.persistence import Customer


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
        select(Customer).where(Customer.customer_name == normalized_name).with_for_update()
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
            select(Customer.id, Customer.customer_name).where(Customer.id.in_(customer_ids))
        )
    }


def customer_ids_matching_name_query(keyword: str) -> Select[tuple[int]]:
    return select(Customer.id).where(Customer.customer_name.ilike(f"%{keyword.strip()}%"))
