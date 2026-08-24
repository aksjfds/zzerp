"""Persistence-free planning port required by customer-order workflows."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class OrderPlanState:
    status: str
    confirmed_at: datetime | None


class SalesPlanningPort(Protocol):
    def order_plan_states(
        self,
        session: Any,
        order_ids: set[int],
    ) -> dict[int, OrderPlanState]: ...

    def order_plan_state(
        self,
        session: Any,
        order_id: int,
        *,
        for_update: bool = False,
    ) -> OrderPlanState | None: ...

    def planned_product_quantities(
        self,
        session: Any,
        customer_order_item_ids: list[int],
    ) -> dict[int, int]: ...

    def delete_order_plan(self, session: Any, order_id: int) -> None: ...
    def rebuild_order_plan(self, session: Any, order: Any) -> Any: ...
    def cancel_order_plan(
        self,
        session: Any,
        order: Any,
        actor_username: str,
    ) -> None: ...
    def confirm_order_plan(
        self,
        session: Any,
        order: Any,
        *,
        expected_revision: int,
        actor_username: str,
    ) -> Any: ...


__all__ = ["OrderPlanState", "SalesPlanningPort"]
