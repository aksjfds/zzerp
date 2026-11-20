from typing import Literal

from pydantic import Field

from schemas.planning import DepartmentLedgerMovement, PlanningModel

OperationKind = Literal['movement', 'inspection', 'rework', 'warehouse', 'outsource', 'outsource_return', 'purchase', 'purchase_receipt']


class RevokeOperation(PlanningModel):
    reason: str = Field(min_length=1, max_length=1000)


class OperationRow(PlanningModel):
    kind: OperationKind
    id: int
    label: str
    order_no: str
    product: str
    material: str
    quantity: str
    actor_username: str
    created_at: str
    note: str
    revoked_at: str | None
    revoked_by: str | None
    revoke_reason: str | None


class DepartmentLedgerRecord(OperationRow):
    counterpart: str
    can_revoke: bool
    revoke_blocker: str | None
    movement: DepartmentLedgerMovement | None


class DepartmentLedgerEnvelope(PlanningModel):
    data: list[DepartmentLedgerRecord]
    total: int
