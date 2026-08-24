from decimal import Decimal

from pydantic import Field

from schemas.common import WorkOrderStatus
from schemas.production_base import ProductionModel


class WorkerResponse(ProductionModel):
    id: int
    worker_name: str
    department_id: int
    workshop_id: int | None


class WorkerListEnvelope(ProductionModel):
    data: list[WorkerResponse]


class DepartmentWorkerResponse(WorkerResponse):
    department_name: str
    department_code: str
    workshop_name: str | None


class DepartmentWorkerWorkshopResponse(ProductionModel):
    id: int
    department_id: int
    workshop_name: str


class DepartmentWorkerOverviewResponse(ProductionModel):
    department_id: int
    department_name: str
    department_code: str
    workshops: list[DepartmentWorkerWorkshopResponse]
    workers: list[DepartmentWorkerResponse]


class DepartmentWorkerOverviewEnvelope(ProductionModel):
    data: DepartmentWorkerOverviewResponse


class DepartmentWorkerCreate(ProductionModel):
    worker_name: str = Field(min_length=1, max_length=100)
    workshop_id: int | None = Field(default=None, gt=0)


class DepartmentWorkerEnvelope(ProductionModel):
    data: DepartmentWorkerResponse


class DepartmentWorkerHistoryItem(ProductionModel):
    work_order_id: int
    work_order_no: str | None
    item_name: str
    procedure_name: str
    planned_quantity: int
    completed_quantity: int
    processing_quantity: int
    completion_rate: float
    lost_quantity: int
    scrap_quantity: int
    status: WorkOrderStatus
    completed_at: str | None


class DepartmentWorkerHistoryEnvelope(ProductionModel):
    data: list[DepartmentWorkerHistoryItem]


class DepartmentWorkerPayItem(ProductionModel):
    item_name: str
    procedure_name: str
    qualified_quantity: int
    unit_price: Decimal | None
    pay_amount: Decimal | None


class DepartmentWorkerPaySummary(ProductionModel):
    worker_id: int
    month: str
    qualified_quantity: int
    total_pay: Decimal
    unpriced_quantity: int
    items: list[DepartmentWorkerPayItem]


class DepartmentWorkerPayEnvelope(ProductionModel):
    data: DepartmentWorkerPaySummary
