from typing import Literal, Self

from pydantic import Field, model_validator

from domain.production_types import WorkOrderCompletionAction, WorkOrderType
from schemas.common import WorkOrderStatus
from schemas.production_base import ProductionModel
from schemas.production_quality import WorkOrderBatchResponse


class WorkOrderCreate(ProductionModel):
    repository_id: int = Field(gt=0)
    procedure_id: int | None = Field(default=None, gt=0)
    procedure_name: str | None = Field(default=None, max_length=200)
    is_temporary: bool
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        has_name = bool((self.procedure_name or "").strip())
        if self.is_temporary:
            if self.procedure_id is not None or not has_name:
                raise ValueError("临时工单必须且只能填写临时工艺名称")
        elif self.procedure_id is None or has_name:
            raise ValueError("普通工单必须且只能选择已配置工艺")
        return self


class AssemblyMaterialInput(ProductionModel):
    repository_id: int = Field(gt=0)
    quantity: int = Field(ge=0)


class AssemblyWorkOrderCreate(ProductionModel):
    materials: list[AssemblyMaterialInput] = Field(min_length=1)
    procedure_id: int | None = Field(default=None, gt=0)
    procedure_name: str | None = Field(default=None, max_length=200)
    is_temporary: bool
    quantity: int = Field(gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_procedure(self) -> Self:
        has_name = bool((self.procedure_name or "").strip())
        if self.is_temporary:
            if self.procedure_id is not None or not has_name:
                raise ValueError("临时工单必须且只能填写临时工艺名称")
        elif self.procedure_id is None or has_name:
            raise ValueError("普通工单必须且只能选择已配置工艺")
        return self


class WorkOrderSubmission(ProductionModel):
    completion_action: WorkOrderCompletionAction


class ReworkSubmission(ProductionModel):
    quantity: int = Field(gt=0)


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
    production_item_id: int
    procedure_id: int | None
    flow_node_id: str
    source_flow_node_id: str | None
    work_order_type: WorkOrderType
    is_temporary: bool
    supplier_name: str | None
    supplier_process_name: str | None
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
    created_by: str
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
    status: WorkOrderStatus
    created_at: str
    closed_at: str | None
    batches: list[WorkOrderBatchResponse]
    undo_operation: ProductionUndoOperationResponse | None = None


class WorkOrderEnvelope(ProductionModel):
    data: WorkOrderResponse
