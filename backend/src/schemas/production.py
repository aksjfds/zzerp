from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.organization import ProcedureSubstepResponse


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RepositoryResponse(ProductionModel):
    card_key: str
    repository_id: int | None
    stage_stock_id: int | None = None
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
    completed_substep_id: int | None = None
    current_stage_name: str | None = None
    available_substeps: list[ProcedureSubstepResponse] = Field(default_factory=list)
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    quantity: int
    available_quantity: int
    assembly_unit_quantity: int
    assembly_required_source_ids: list[str]
    assembly_group_complete: bool
    delivery_date: date
    arrived_at: str | None
    work_status: Literal["unprocessed", "processing", "completed"]
    can_create_work_order: bool
    can_dispatch: bool = False


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
    repository_id: int | None = Field(default=None, gt=0)
    procedure_stage_stock_id: int | None = Field(default=None, gt=0)
    substep_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.repository_id is None) == (self.procedure_stage_stock_id is None):
            raise ValueError("repository_id 和 procedure_stage_stock_id 必须且只能提供一个")
        return self


class AssemblyWorkOrderCreate(ProductionModel):
    repository_ids: list[int] = Field(min_length=2)
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)


class WorkOrderSubmission(ProductionModel):
    quantity: int = Field(gt=0)
    completion_action: Literal["direct", "qc"]


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
    source_substep_id: int | None
    qualified_quantity: int | None
    rework_quantity: int | None
    scrap_quantity: int | None
    lost_quantity: int | None
    qc_worker_id: int | None
    qc_worker_name: str | None
    defect_reason: str | None
    recorded_at: str | None


class WorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    repository_id: int | None
    procedure_stage_stock_id: int | None
    production_item_id: int
    flow_node_id: str
    source_flow_node_id: str | None
    substep_id: int | None
    work_order_type: Literal["substep", "assembly"]
    input_production_item_ids: list[int]
    customer_order_no: str
    part_no: str
    part_name: str
    work_order_name: str
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
    work_order_name: str
    remaining_quantity: int


class PendingQcListEnvelope(ProductionModel):
    data: list[PendingQcResponse]
    total: int


class SubstepOpenWorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    worker_id: int | None
    worker_name: str | None
    quantity: int
    processing_quantity: int


class SubstepCardResponse(ProductionModel):
    card_key: str
    production_item_id: int
    flow_node_id: str
    source_flow_node_id: str
    procedure_id: int
    substep_id: int | None
    substep_name: str
    repository_id: int | None
    stage_stock_id: int | None
    available_quantity: int
    processing_quantity: int
    pending_qc_quantity: int
    completed_quantity: int
    can_create_work_order: bool
    can_submit_qc: bool
    open_work_orders: list[SubstepOpenWorkOrderResponse] = Field(default_factory=list)


class SubstepCardListEnvelope(ProductionModel):
    data: list[SubstepCardResponse]


class ProcedureDispatchCreate(ProductionModel):
    quantity: int = Field(gt=0)


class ProcedureDispatchResponse(ProductionModel):
    stage_stock_id: int
    production_item_id: int
    substep_id: int
    quantity: int
    target_flow_node_id: str | None
    target_department_id: int | None


class ProcedureDispatchEnvelope(ProductionModel):
    data: ProcedureDispatchResponse
