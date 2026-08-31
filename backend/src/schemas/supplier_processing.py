from pydantic import Field, field_validator

from domain.production_types import WorkOrderStatus
from schemas.production_base import ProductionModel
from schemas.production_quality import WorkOrderBatchResponse


class SupplierProcessingTaskResponse(ProductionModel):
    production_plan_id: int
    production_plan_item_id: int
    production_item_id: int
    customer_order_item_id: int
    product_id: int
    product_version: int
    product_bom_id: int
    source_flow_node_id: str
    supplier_flow_node_id: str
    department_id: int
    item_code: str
    item_name: str
    task_quantity: int
    plan_status: str
    work_order_id: int | None
    work_order_status: WorkOrderStatus | None
    can_create_work_order: bool


class SupplierProcessingTaskListEnvelope(ProductionModel):
    data: list[SupplierProcessingTaskResponse]
    total: int


class SupplierProcessingWorkOrderCreate(ProductionModel):
    production_plan_item_id: int = Field(gt=0)
    supplier_flow_node_id: str = Field(min_length=1, max_length=200)
    supplier_name: str = Field(min_length=1, max_length=200)
    supplier_process_name: str = Field(min_length=1, max_length=200)
    remark: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "supplier_flow_node_id",
        "supplier_name",
        "supplier_process_name",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("内容不能为空")
        return normalized

    @field_validator("remark")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None


class SupplierProcessingQcTaskResponse(ProductionModel):
    production_plan_id: int
    production_plan_item_id: int
    production_item_id: int
    customer_order_item_id: int
    product_id: int
    product_version: int
    product_bom_id: int
    source_flow_node_id: str
    supplier_flow_node_id: str
    item_code: str
    item_name: str
    work_order_id: int
    work_order_no: str
    supplier_name: str
    supplier_process_name: str
    remark: str | None
    task_quantity: int
    inspected_quantity: int
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    remaining_qualified_quantity: int
    pending_destination_quantity: int
    released_quantity: int
    status: WorkOrderStatus
    created_at: str
    batches: list[WorkOrderBatchResponse]


class SupplierProcessingQcTaskListEnvelope(ProductionModel):
    data: list[SupplierProcessingQcTaskResponse]
    total: int


class SupplierProcessingQcInspection(ProductionModel):
    qc_worker_id: int = Field(gt=0)
    qualified_quantity: int = Field(ge=0)
    rework_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    defect_reason: str | None = Field(default=None, max_length=1000)
