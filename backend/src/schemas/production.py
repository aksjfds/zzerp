from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.organization import ProcedureResponse


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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
    node_type: str
    source_flow_node_id: str
    source_node_label: str
    material_source_name: str
    workshop_id: int
    available_procedures: list[ProcedureResponse] = Field(default_factory=list)
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    quantity: int
    available_quantity: int
    assembly_unit_quantity: int
    assembly_required_source_ids: list[str]
    assembly_material_key: str
    assembly_required_material_keys: list[str]
    assembly_group_complete: bool
    assembly_output_name: str | None = None
    delivery_date: date
    arrived_at: str | None
    work_status: Literal[
        "unprocessed",
        "processing",
        "processing_completed",
        "qc",
        "rework",
        "completed",
    ]
    can_create_work_order: bool


class RepositoryListEnvelope(ProductionModel):
    data: list[RepositoryResponse]
    total: int


class WarehouseStorageInput(ProductionModel):
    production_item_id: int = Field(gt=0)
    flow_node_id: str = Field(min_length=1, max_length=200)
    source_flow_node_id: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)


class WarehouseStorageResponse(ProductionModel):
    inventory_stock_id: int
    quantity: int
    completed_flow_node_id: str
    completed_node_label: str


class DepartmentSurplusInventoryItem(ProductionModel):
    key: str
    source_kind: Literal["production", "qc"]
    batch_id: int | None
    production_item_id: int
    customer_order_no: str
    product_code: str
    product_name: str
    product_version: int
    item_type: Literal["part", "assembly"]
    item_code: str
    item_name: str
    department_code: str
    flow_node_id: str
    source_flow_node_id: str
    current_node_label: str
    completed_flow_node_id: str
    completed_node_label: str
    quantity: int


class DepartmentSurplusInventoryEnvelope(ProductionModel):
    data: list[DepartmentSurplusInventoryItem]


class AssemblyMaterialArrivalResponse(ProductionModel):
    material_type: Literal["part", "assembly"]
    material_no: str
    material_name: str
    task_quantity: int
    arrived_quantity: int


class DepartmentProductionProgressResponse(ProductionModel):
    production_plan_item_id: int
    production_item_id: int | None
    flow_node_id: str | None
    part_no: str
    part_name: str
    processing_workshop: str
    task_quantity: int
    arrived_quantity: int
    material_arrivals: list[AssemblyMaterialArrivalResponse]
    completed_quantity: int
    remark: str


class DepartmentProductionProgressEnvelope(ProductionModel):
    data: list[DepartmentProductionProgressResponse]
    total: int


class ProductionProgressWorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    worker_name: str | None
    quantity: int
    processed_quantity: int
    submitted_quantity: int
    pending_qc_quantity: int
    completed_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    status: Literal["open", "closed", "cancelled"]
    created_at: str
    closed_at: str | None


class ProductionProgressProcedureCardResponse(ProductionModel):
    card_key: str
    card_type: Literal["process", "assembly", "purchase"]
    sort_order: int
    flow_node_id: str
    procedure_id: int | None
    card_name: str
    department_code: str
    department_name: str
    workshop_name: str
    procedure_name: str
    status: Literal[
        "not_arrived",
        "ready",
        "processing",
        "pending_qc",
        "completed",
        "exception",
    ]
    task_quantity: int
    arrived_quantity: int
    processing_quantity: int
    ready_for_qc_quantity: int
    pending_qc_quantity: int
    completed_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    work_orders: list[ProductionProgressWorkOrderResponse]


class ProductionProgressItemDetailResponse(ProductionModel):
    production_plan_item_id: int
    production_item_ids: list[int]
    customer_order_no: str
    factory_code: str
    product_name: str
    part_no: str
    part_name: str
    plan_status: Literal["draft", "confirmed", "cancelled"]
    task_quantity: int
    cards: list[ProductionProgressProcedureCardResponse]


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


class WorkOrderCreate(ProductionModel):
    repository_id: int = Field(gt=0)
    procedure_id: int | None = Field(default=None, gt=0)
    procedure_name: str | None = Field(default=None, max_length=200)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.procedure_id is None) == (not (self.procedure_name or "").strip()):
            raise ValueError("procedure_id 和 procedure_name 必须且只能提供一个")
        return self


class AssemblyMaterialInput(ProductionModel):
    repository_id: int = Field(gt=0)
    quantity: int = Field(ge=0)


class AssemblyWorkOrderCreate(ProductionModel):
    materials: list[AssemblyMaterialInput] = Field(min_length=1)
    procedure_id: int | None = Field(default=None, gt=0)
    procedure_name: str | None = Field(default=None, max_length=200)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_procedure(self) -> Self:
        if (self.procedure_id is None) == (not (self.procedure_name or "").strip()):
            raise ValueError("procedure_id 和 procedure_name 必须且只能提供一个")
        return self


class WorkOrderSubmission(ProductionModel):
    quantity: int = Field(gt=0)
    completion_action: Literal["direct", "qc"]


class PurchaseArrival(ProductionModel):
    quantity: int = Field(gt=0)


class ReworkSubmission(ProductionModel):
    quantity: int = Field(gt=0)


class QcInspection(ProductionModel):
    qc_worker_id: int = Field(gt=0)
    qualified_quantity: int = Field(ge=0)
    rework_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    defect_reason: str | None = None
    qualified_disposition: Literal["return", "release"] | None = None

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        if (self.qualified_quantity > 0) != (self.qualified_disposition is not None):
            raise ValueError("存在合格数量时必须且只能选择一个合格品去向")
        return self


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
    qualified_disposition: Literal["return", "release"] | None
    recorded_at: str | None


class ProductionUndoOperationResponse(ProductionModel):
    id: int
    work_order_batch_id: int | None
    operation_type: Literal["purchase_arrival", "submission", "rework_submission"]
    operation_label: str
    actor_username: str
    created_at: str


class WorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    repository_id: int | None
    production_item_id: int
    procedure_id: int
    flow_node_id: str
    source_flow_node_id: str | None
    work_order_type: Literal["standard", "purchase_receipt", "assembly"]
    qc_available: bool
    direct_result_allowed: bool
    input_production_item_ids: list[int]
    customer_order_no: str
    factory_code: str
    product_name: str
    part_no: str
    part_name: str
    procedure_name: str
    work_order_name: str
    remark: str
    worker_id: int | None
    worker_name: str | None
    quantity: int
    output_unit_quantity: int
    output_quantity: int
    processed_quantity: int
    submitted_quantity: int
    ready_for_qc_quantity: int
    processing_quantity: int
    processing_output_quantity: int
    ready_output_quantity: int
    pending_qc_quantity: int
    qualified_quantity: int
    qualified_output_quantity: int
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


class PendingQcListEnvelope(ProductionModel):
    data: list[PendingQcResponse]
    total: int
