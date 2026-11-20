from uuid import UUID

from pydantic import Field

from schemas.planning import DepartmentWorkOrderResponse, PlanningModel


class PurchaseCreate(PlanningModel):
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    note: str = Field(default='', max_length=1000)
    request_id: UUID


class PurchaseCommandEnvelope(PlanningModel):
    id: int


class PurchaseRecord(PlanningModel):
    id: int
    quantity: str
    note: str
    actor_username: str
    created_at: str
    received_quantity: str
    received: bool


class PurchaseWorkOrder(DepartmentWorkOrderResponse):
    purchases: list[PurchaseRecord]


class PurchaseWorkOrderEnvelope(PlanningModel):
    data: list[PurchaseWorkOrder]
    total: int
