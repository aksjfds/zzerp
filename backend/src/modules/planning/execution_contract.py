from typing import Protocol

from sqlalchemy.orm import Session


class PlanExecutionCollaborators(Protocol):
    def reserve_plan_item(self, session: Session, **kwargs) -> int: ...
    def release_plan_reservations(
        self, session: Session, production_plan_id: int, actor_username: str
    ) -> None: ...
    def initialize_order_production(self, session: Session, order, **kwargs) -> None: ...
    def cancel_order_production(self, session: Session, order) -> None: ...


__all__ = ["PlanExecutionCollaborators"]
