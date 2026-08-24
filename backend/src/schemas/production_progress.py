from typing import Literal

from schemas.production_base import ProductionModel


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
