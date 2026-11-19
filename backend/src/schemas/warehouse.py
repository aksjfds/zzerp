from uuid import UUID

from pydantic import Field

from schemas.planning import PlanningModel


class WarehouseDispatchCreate(PlanningModel):
    product_id: int = Field(gt=0)
    material_key: str = Field(pattern=r'^[0-9a-f]{64}$')
    warehouse_order_id: int = Field(gt=0)
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    request_id: UUID
    note: str = Field(default='', max_length=1000)


class WarehouseDispatchEnvelope(PlanningModel):
    id: int


class WarehouseStock(PlanningModel):
    id: int
    arrival_date: str
    product_id: int
    material_key: str
    product: str
    material: str
    available_quantity: str


class WarehouseStocksEnvelope(PlanningModel):
    data: list[WarehouseStock]
    total: int


class WarehousePickRow(PlanningModel):
    id: int
    order_no: str
    product: str
    material: str
    quantity: str
    department: str
    actor_username: str
    created_at: str
    sources: str
    note: str


class WarehousePicksEnvelope(PlanningModel):
    data: list[WarehousePickRow]
    total: int


class WarehouseDispatchPlan(PlanningModel):
    id: int
    order_no: str


class WarehouseDispatchPlansEnvelope(PlanningModel):
    data: list[WarehouseDispatchPlan]


class WarehouseDispatchTarget(PlanningModel):
    target_order_id: int
    warehouse_order_id: int
    department: str
    material: str
    available_quantity: str


class WarehouseDispatchTargetsEnvelope(PlanningModel):
    data: list[WarehouseDispatchTarget]
