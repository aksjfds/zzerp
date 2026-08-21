from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AdminModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminWorkerResponse(AdminModel):
    id: int
    worker_name: str
    department_id: int
    department_name: str
    department_code: str
    workshop_id: int | None
    workshop_name: str | None


class AdminWorkerDepartmentResponse(AdminModel):
    department_id: int
    department_name: str
    department_code: str
    workers: list[AdminWorkerResponse]


class AdminWorkerOverviewEnvelope(AdminModel):
    data: list[AdminWorkerDepartmentResponse]


class AdminWorkerHistoryItem(AdminModel):
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
    status: str
    completed_at: str | None


class AdminWorkerHistoryEnvelope(AdminModel):
    data: list[AdminWorkerHistoryItem]


class AdminWorkerPayItem(AdminModel):
    item_name: str
    procedure_name: str
    qualified_quantity: int
    unit_price: Decimal | None
    pay_amount: Decimal | None


class AdminWorkerPaySummary(AdminModel):
    worker_id: int
    month: str
    qualified_quantity: int
    total_pay: Decimal
    unpriced_quantity: int
    items: list[AdminWorkerPayItem]


class AdminWorkerPayEnvelope(AdminModel):
    data: AdminWorkerPaySummary
