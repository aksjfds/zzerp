from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryResponse(ProductionModel):
    card_key: str
    repository_id: int | None
    production_item_id: int
    customer_order_item_id: int
    customer_order_no: str
    customer_name: str
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    product_bom_id: int | None
    part_name: str
    part_no: str
    flow_node_id: str
    source_flow_node_id: str
    source_node_label: str
    procedure_name: str
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    quantity: int
    available_quantity: int
    assembly_unit_quantity: int
    delivery_date: date
    arrived_at: str | None
    work_status: Literal["unprocessed", "processing", "completed"]
    can_create_work_order: bool


class RepositoryListEnvelope(ProductionModel):
    data: list[RepositoryResponse]
    total: int


class WorkerResponse(ProductionModel):
    id: int
    worker_name: str
    department_id: int
    workshop_id: int | None


class WorkerListEnvelope(ProductionModel):
    data: list[WorkerResponse]


class WorkOrderCreate(ProductionModel):
    repository_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)


class AssemblyWorkOrderCreate(ProductionModel):
    repository_ids: list[int] = Field(min_length=2)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)


class WorkOrderSubmission(ProductionModel):
    quantity: int = Field(gt=0)


class QcInspection(ProductionModel):
    qc_worker_id: int = Field(gt=0)
    qualified_quantity: int = Field(ge=0)
    rework_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    defect_reason: str | None = None


class WorkOrderBatchResponse(ProductionModel):
    id: int
    work_order_id: int
    submitted_quantity: int
    flow_node_id: str
    qualified_quantity: int | None
    rework_quantity: int | None
    scrap_quantity: int | None
    lost_quantity: int | None
    qc_worker_name: str | None
    defect_reason: str | None
    recorded_at: str | None


class WorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    repository_id: int | None
    production_item_id: int
    input_production_item_ids: list[int]
    customer_order_no: str
    part_no: str
    part_name: str
    procedure_name: str
    worker_id: int | None
    worker_name: str | None
    quantity: int
    submitted_quantity: int
    processing_quantity: int
    pending_qc_quantity: int
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    status: str
    created_at: str
    closed_at: str | None
    batches: list[WorkOrderBatchResponse]


class WorkOrderEnvelope(ProductionModel):
    data: WorkOrderResponse


class WorkOrderListEnvelope(ProductionModel):
    data: list[WorkOrderResponse]
    total: int


class WorkOrderBatchEnvelope(ProductionModel):
    data: WorkOrderBatchResponse


class PendingQcResponse(WorkOrderBatchResponse):
    repository_id: int | None
    production_item_id: int
    work_order_no: str
    customer_order_no: str
    part_no: str
    part_name: str
    procedure_name: str
    remaining_quantity: int


class PendingQcListEnvelope(ProductionModel):
    data: list[PendingQcResponse]
    total: int
