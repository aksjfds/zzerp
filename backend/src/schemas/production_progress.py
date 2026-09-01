from typing import Literal

from schemas.production_base import ProductionModel
from schemas.production_work_orders import WorkOrderResponse


class AssemblyMaterialArrivalResponse(ProductionModel):
    material_type: Literal["part", "assembly"]
    material_no: str
    material_name: str
    task_quantity: int
    arrived_quantity: int


class ProductionTaskWorkOrderContributionResponse(ProductionModel):
    work_order_id: int
    quantity: int


class ProductionTaskBatchContributionResponse(ProductionModel):
    batch_id: int
    quantity: int


class ProductionTaskProcessingStatusResponse(ProductionModel):
    status: Literal[
        "not_started",
        "processing",
        "submitted_qc",
        "rework",
        "completed",
        "exception",
        "department_completed",
    ]
    label: str
    action: Literal[
        "create_work_order",
        "view_work_orders",
        "none",
    ]
    quantity: int
    procedure_names: list[str]
    repository_ids: list[int]
    related_work_orders: list[ProductionTaskWorkOrderContributionResponse]
    related_batches: list[ProductionTaskBatchContributionResponse]
    creation_mode: Literal["repository", "assembly_initial"] | None


class DepartmentProductionProgressResponse(ProductionModel):
    production_plan_item_id: int
    customer_order_item_id: int
    production_item_id: int | None
    flow_node_id: str
    plan_status: Literal["draft", "confirmed", "cancelled", "completed"]
    part_no: str
    part_name: str
    processing_workshop_id: int
    processing_workshop: str
    task_quantity: int
    arrived_quantity: int
    material_arrivals: list[AssemblyMaterialArrivalResponse]
    processing_statuses: list[ProductionTaskProcessingStatusResponse]
    completed_quantity: int
    remark: str


class DepartmentProductionProgressEnvelope(ProductionModel):
    data: list[DepartmentProductionProgressResponse]
    total: int


class ProductionProgressWorkOrderResponse(ProductionModel):
    id: int
    work_order_no: str
    work_order_type: Literal["standard", "assembly", "supplier_processing"]
    is_temporary: bool
    qc_available: bool
    direct_result_allowed: bool
    output_unit_quantity: int
    procedure_name: str
    workshop_name: str
    worker_name: str | None
    work_order_quantity: int
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
    work_order: WorkOrderResponse


class ProductionProgressProcedureCardResponse(ProductionModel):
    card_key: str
    card_type: Literal["process", "assembly"]
    sort_order: int
    flow_node_id: str
    procedure_id: int | None
    card_name: str
    department_code: str
    department_name: str
    workshop_id: int | None
    workshop_name: str
    procedure_name: str
    status: Literal["not_arrived", "ready", "processing", "pending_qc", "completed", "exception"]
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
    plan_status: Literal["draft", "confirmed", "cancelled", "completed"]
    task_quantity: int
    cards: list[ProductionProgressProcedureCardResponse]
    work_orders: list[ProductionProgressWorkOrderResponse]
