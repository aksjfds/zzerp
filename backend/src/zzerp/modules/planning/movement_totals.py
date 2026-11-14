"""One database aggregation for parent balances, component receipts and issue capacity."""

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zzerp.modules.planning.persistence import DepartmentWorkOrderMovement


@dataclass(slots=True)
class MovementTotals:
    receipts: dict[str, int] = field(default_factory=dict)
    issued: int = 0


def load_movement_totals(session: Session, order_ids: set[int]) -> dict[int, MovementTotals]:
    if not order_ids:
        return {}
    rows = session.execute(
        select(
            DepartmentWorkOrderMovement.work_order_id,
            DepartmentWorkOrderMovement.direction,
            DepartmentWorkOrderMovement.input_material_node_id,
            func.sum(DepartmentWorkOrderMovement.quantity),
        )
        .where(DepartmentWorkOrderMovement.work_order_id.in_(order_ids))
        .group_by(
            DepartmentWorkOrderMovement.work_order_id,
            DepartmentWorkOrderMovement.direction,
            DepartmentWorkOrderMovement.input_material_node_id,
        )
    )
    totals: dict[int, MovementTotals] = {}
    for order_id, direction, material, quantity in rows:
        total = totals.setdefault(order_id, MovementTotals())
        if direction == "receipt":
            total.receipts[material] = int(quantity)
        else:
            total.issued += int(quantity)
    return totals
