"""Exact unit/kit capacity from immutable movement quantities."""

from collections.abc import Mapping

from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import HandoffContext
from zzerp.modules.organization.api import allows_receipts
from zzerp.modules.planning.movement_totals import MovementTotals, load_movement_totals
from zzerp.modules.planning.persistence import DepartmentWorkOrder


def remaining_issue_quantity(
    material_id: str,
    requirements: Mapping[str, Mapping[str, int]],
    receipts: Mapping[str, int],
    issued: int,
) -> int:
    target = requirements[material_id]
    components = {part: 0 for part in target}
    for incoming, quantity in receipts.items():
        if incoming not in requirements or not requirements[incoming].keys() <= target.keys():
            raise DomainError(
                "issue_input_inconsistent",
                "到料组成与当前工单不一致，请检查工程资料",
                status_code=409,
            )
        for part, units in requirements[incoming].items():
            components[part] += quantity * units
    kits = min(components[part] // units for part, units in target.items())
    return kits - issued


def available_issue_quantity(
    session: Session,
    order: DepartmentWorkOrder,
    context: HandoffContext,
    department_code: str,
) -> int | None:
    if not allows_receipts(department_code):
        return None
    total = load_movement_totals(session, {order.id}).get(order.id, MovementTotals())
    return remaining_issue_quantity(
        order.material_node_id, context.requirements, total.receipts, total.issued
    )
