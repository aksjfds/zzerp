from sqlalchemy import select
from sqlalchemy.orm import Session

from zzerp.modules.sales.persistence import Customer
from zzerp.time import business_iso


def list_customers(session: Session, keyword: str | None = None) -> list[dict]:
    statement = select(Customer).order_by(Customer.customer_name, Customer.id)
    normalized = (keyword or "").strip()
    if normalized:
        statement = statement.where(Customer.customer_name.ilike(f"%{normalized}%"))
    return [serialize_customer(item) for item in session.scalars(statement).all()]


def serialize_customer(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "customer_name": customer.customer_name,
        "created_at": business_iso(customer.created_at),
        "updated_at": business_iso(customer.updated_at),
    }
