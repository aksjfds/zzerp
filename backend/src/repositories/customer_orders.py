from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.sales import CustomerOrder


class CustomerOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[CustomerOrder]:
        return list(
            self.session.scalars(
                select(CustomerOrder)
                .options(selectinload(CustomerOrder.items))
                .order_by(CustomerOrder.updated_at.desc(), CustomerOrder.id.desc())
            ).all()
        )

    def get(self, order_id: int) -> CustomerOrder | None:
        return self.session.scalar(
            select(CustomerOrder)
            .options(selectinload(CustomerOrder.items))
            .where(CustomerOrder.id == order_id)
        )

    def add(self, order: CustomerOrder) -> None:
        self.session.add(order)

    def delete(self, order: CustomerOrder) -> None:
        self.session.delete(order)
