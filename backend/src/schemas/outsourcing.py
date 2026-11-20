from typing import Literal
from uuid import UUID

from pydantic import Field

from schemas.planning import PlanningModel


class OutsourceDispatchCreate(PlanningModel):
    receipt_id: int = Field(gt=0)
    process: Literal['etching', 'plating']
    vendor: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    note: str = Field(default='', max_length=1000)
    request_id: UUID


class OutsourceReturnCreate(PlanningModel):
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    note: str = Field(default='', max_length=1000)
    request_id: UUID


class OutsourceCommandEnvelope(PlanningModel):
    id: int


class OutsourceReturnRow(PlanningModel):
    id: int
    quantity: str
    actor_username: str
    created_at: str
    note: str


class OutsourceDispatchRow(OutsourceReturnRow):
    process: Literal['etching', 'plating']
    vendor: str
    returned_quantity: str
    returns: list[OutsourceReturnRow]


class OutsourceReceiptRow(PlanningModel):
    id: int
    order_no: str
    product: str
    material: str
    plan_status: str
    quantity: str
    dispatched_quantity: str
    created_at: str
    dispatches: list[OutsourceDispatchRow]


class OutsourceReceiptEnvelope(PlanningModel):
    data: list[OutsourceReceiptRow]
    total: int
