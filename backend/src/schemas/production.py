from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.organization import ProcedureTagResponse


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RepositoryResponse(ProductionModel):
    card_key: str
    repository_id: int | None
    tag_stock_id: int | None = None
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
    procedure_id: int | None
    procedure_name: str
    current_tag_set_name: str | None = None
    available_tags: list[ProcedureTagResponse] = Field(default_factory=list)
    configured_tags: list[ProcedureTagResponse] = Field(default_factory=list)
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    quantity: int
    available_quantity: int
    assembly_unit_quantity: int
    assembly_required_source_ids: list[str]
    assembly_group_complete: bool
    assembly_output_name: str | None = None
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
    status: str
    completed_at: str | None


class DepartmentWorkerHistoryEnvelope(ProductionModel):
    data: list[DepartmentWorkerHistoryItem]


class WorkOrderCreate(ProductionModel):
    repository_id: int | None = Field(default=None, gt=0)
    procedure_tag_stock_id: int | None = Field(default=None, gt=0)
    tag_names: list[str] = Field(default_factory=list, max_length=20)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.repository_id is None) == (self.procedure_tag_stock_id is None):
            raise ValueError("repository_id 和 procedure_tag_stock_id 必须且只能提供一个")
        return self


class AssemblyWorkOrderCreate(ProductionModel):
    repository_ids: list[int] = Field(min_length=2)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)


class WorkOrderSubmission(ProductionModel):
    quantity: int = Field(gt=0)
    completion_action: Literal["direct", "qc"]


class ReworkSubmission(ProductionModel):
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
    source_flow_node_id: str
    rework_source_batch_id: int | None
    rework_pending_quantity: int
    qualified_quantity: int | None
    rework_quantity: int | None
    scrap_quantity: int | None
    lost_quantity: int | None
    qc_worker_id: int | None
    qc_worker_name: str | None
    defect_reason: str | None
    recorded_at: str | None


class ProductionUndoOperationResponse(ProductionModel):
    id: int
    work_order_batch_id: int | None
    operation_type: Literal["submission", "rework_submission"]
    operation_label: str
    actor_username: str
    created_at: str


class WorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    repository_id: int | None
    procedure_tag_stock_id: int | None
    production_item_id: int
    procedure_id: int | None
    flow_node_id: str
    source_flow_node_id: str | None
    applied_tag_set_id: int | None
    source_tag_set_id: int | None
    target_tag_set_id: int | None
    work_order_type: Literal["tag", "purchase_receipt", "assembly"]
    qc_required: bool
    input_production_item_ids: list[int]
    customer_order_no: str
    part_no: str
    part_name: str
    work_order_name: str
    remark: str
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
    undo_operation: ProductionUndoOperationResponse | None = None


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
    work_order_name: str
    dispatchable_quantity: int = 0
    target_node_label: str | None = None


class PendingQcListEnvelope(ProductionModel):
    data: list[PendingQcResponse]
    total: int


class QcDispatchCreate(ProductionModel):
    quantity: int = Field(gt=0)


class QcDispatchResponse(ProductionModel):
    batch_id: int
    quantity: int
    remaining_quantity: int
    target_flow_node_id: str
    target_department_id: int


class QcDispatchEnvelope(ProductionModel):
    data: QcDispatchResponse


class TagProcessingDetail(ProductionModel):
    tag_names: list[str]
    tag_set_name: str
    quantity: int


class TagCardResponse(ProductionModel):
    card_key: str
    production_item_id: int
    flow_node_id: str
    source_flow_node_id: str
    procedure_id: int
    tag_set_id: int | None
    tag_ids: list[int]
    tag_names: list[str]
    tag_set_name: str
    repository_id: int | None
    tag_stock_id: int | None
    available_quantity: int
    processing_quantity: int
    pending_qc_quantity: int
    completed_quantity: int
    processing_details: list[TagProcessingDetail]
    can_create_work_order: bool = False


class TagCardListEnvelope(ProductionModel):
    data: list[TagCardResponse]
