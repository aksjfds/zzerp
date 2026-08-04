from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from modules.sales.persistence import CustomerOrder


class CustomerOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        offset: int = 0,
        limit: int = 50,
        statuses: set[str] | None = None,
    ) -> list[CustomerOrder]:
        statement = (
            select(CustomerOrder)
            .options(
                selectinload(CustomerOrder.items),
                selectinload(CustomerOrder.customer),
            )
            .order_by(CustomerOrder.updated_at.desc(), CustomerOrder.id.desc())
        )
        if statuses:
            statement = statement.where(CustomerOrder.status.in_(statuses))
        return list(
            self.session.scalars(
                statement.offset(offset).limit(limit)
            ).all()
        )

    def count(self, statuses: set[str] | None = None) -> int:
        statement = select(func.count(CustomerOrder.id))
        if statuses:
            statement = statement.where(CustomerOrder.status.in_(statuses))
        return self.session.scalar(statement) or 0

    def get(self, order_id: int) -> CustomerOrder | None:
        return self.session.scalar(
            select(CustomerOrder)
            .options(
                selectinload(CustomerOrder.items),
                selectinload(CustomerOrder.customer),
            )
            .where(CustomerOrder.id == order_id)
        )

    def get_for_update(self, order_id: int) -> CustomerOrder | None:
        return self.session.scalar(
            select(CustomerOrder)
            .options(
                selectinload(CustomerOrder.items),
                selectinload(CustomerOrder.customer),
            )
            .where(CustomerOrder.id == order_id)
            .with_for_update()
        )

    def add(self, order: CustomerOrder) -> None:
        self.session.add(order)

    def delete(self, order: CustomerOrder) -> None:
        self.session.delete(order)
