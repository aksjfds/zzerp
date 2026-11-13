from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductionPlanCreate(PlanningModel):
    customer_id: int = Field(gt=0)
    order_no: str = Field(min_length=1, max_length=200)
    order_quantity: int = Field(strict=True, gt=0, le=2147483647)
    product_id: int = Field(gt=0)
    production_quantity: int = Field(strict=True, gt=0, le=2147483647)


class ProductionPlanUpdate(ProductionPlanCreate):
    expected_revision: int = Field(gt=0)


class ProductionPlanResponse(ProductionPlanCreate):
    id: int
    customer_name: str
    product_name: str
    factory_code: str
    status: Literal["draft", "confirmed", "cancelled", "completed"]
    revision: int
    confirmed_at: str | None
    confirmed_by: str | None
    completed_at: str | None
    completed_by: str | None
    created_at: str
    updated_at: str


class ProductionPlanEnvelope(PlanningModel):
    data: ProductionPlanResponse


class ProductionPlanListEnvelope(PlanningModel):
    data: list[ProductionPlanResponse]
    total: int


class WorkOrderComponent(PlanningModel):
    material_node_id: str
    part_no: str
    part_name: str
    required_quantity: str
    received_quantity: str


class DepartmentWorkOrderResponse(PlanningModel):
    id: int
    production_plan_id: int
    material_node_id: str
    department_node_id: str
    order_no: str
    order_quantity: int
    customer_name: str
    product_id: int
    factory_code: str
    product_name: str
    part_no: str
    part_name: str
    department_code: str
    department_name: str
    can_receive: bool
    task_quantity: int
    received_quantity: str
    issued_quantity: str
    plan_status: Literal["draft", "confirmed", "cancelled", "completed"]
    components: list[WorkOrderComponent]


class DepartmentWorkOrderListEnvelope(PlanningModel):
    data: list[DepartmentWorkOrderResponse]
    total: int


class ProgressMaterial(PlanningModel):
    material_node_id: str
    part_no: str
    part_name: str
    work_orders: list[DepartmentWorkOrderResponse]


class ProgressProduct(PlanningModel):
    product_id: int
    factory_code: str
    product_name: str
    materials: list[ProgressMaterial]


class ProductionProgressEnvelope(PlanningModel):
    data: list[ProgressProduct]
    total: int


class DepartmentMovementCreate(PlanningModel):
    direction: Literal["receipt", "issue"]
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    note: str = Field(default="", max_length=1000)
    request_id: UUID
    receipt_source: Literal["external", "ticket"] | None = None
    ticket_id: int | None = Field(default=None, gt=0)
    input_material_node_id: str | None = Field(default=None, min_length=1, max_length=100)
    target_work_order_id: int | None = Field(default=None, gt=0)


class DepartmentMovementResponse(DepartmentMovementCreate):
    receipt_movement_ids: list[int]
    id: int
    actor_username: str
    created_at: str
    ticket_no: str | None
    material_name: str


class HandoffChoice(PlanningModel):
    id: int
    label: str


class ExternalInputChoice(PlanningModel):
    material_node_id: str
    label: str


class HandoffOptionsResponse(PlanningModel):
    available_issue_quantity: str | None
    can_receive: bool
    targets: list[HandoffChoice]
    external_inputs: list[ExternalInputChoice]


class HandoffTicketResponse(PlanningModel):
    can_receive: bool
    id: int
    ticket_no: str
    order_no: str
    factory_code: str
    product_name: str
    material_name: str
    source_department: str
    target_department: str
    quantity: int
    received_quantity: str
    created_at: str
    note: str
    target_work_order_id: int
    plan_status: Literal["draft", "confirmed", "cancelled", "completed"]


class HandoffTicketListEnvelope(PlanningModel):
    data: list[HandoffTicketResponse]
    total: int


class DepartmentMovementEnvelope(PlanningModel):
    data: DepartmentMovementResponse


class DepartmentMovementListEnvelope(PlanningModel):
    data: list[DepartmentMovementResponse]
    total: int


class DepartmentLedgerMovement(DepartmentMovementResponse):
    order_no: str
    factory_code: str
    product_name: str
    department_name: str


class DepartmentLedgerEnvelope(PlanningModel):
    data: list[DepartmentLedgerMovement]
    total: int
