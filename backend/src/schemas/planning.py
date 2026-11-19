from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.engineering import ProcessFlowPayload


class PlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductionPlanItemCreate(PlanningModel):
    source_version: int | None = Field(default=None, gt=0)
    order_quantity: int = Field(strict=True, gt=0, le=2147483647)
    product_id: int = Field(gt=0)
    production_quantity: int = Field(strict=True, gt=0, le=2147483647)


class ProductionPlanCreate(PlanningModel):
    customer_id: int = Field(gt=0)
    order_no: str = Field(min_length=1, max_length=200)
    order_date: date
    delivery_date: date
    items: list[ProductionPlanItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_products(self):
        if self.delivery_date < self.order_date:
            raise ValueError("交货日期不能早于下单日期")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("同一计划不能重复选择产品")
        return self


class ProductionPlanUpdate(ProductionPlanCreate):
    expected_revision: int = Field(gt=0)


class ProductionPlanItemResponse(ProductionPlanItemCreate):
    source_version: int
    source_version_value: str
    customer_code: str
    product_name: str
    factory_code: str


class ProductionPlanResponse(ProductionPlanCreate):
    items: list[ProductionPlanItemResponse]
    id: int
    customer_name: str
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


class WorkOrderScheduleUpdate(PlanningModel):
    expected_revisions: dict[int, int] = Field(default_factory=dict)
    scheduled_date: date | None
    expected_revision: int = Field(gt=0)


class WorkOrderScheduleResponse(PlanningModel):
    id: int
    scheduled_date: date | None
    schedule_revision: int


class WorkOrderScheduleEnvelope(PlanningModel):
    data: list[WorkOrderScheduleResponse]


class DepartmentWorkOrderResponse(PlanningModel):
    upstream_departments: list[str]
    downstream_departments: list[str]
    can_issue: bool
    requires_inspection: bool
    good_quantity: str
    scrap_quantity: str
    rework_quantity: str
    scheduled_date: date | None
    schedule_revision: int
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
    order_quantity: int
    task_quantity: int
    material_node_id: str
    part_no: str
    part_name: str
    work_orders: list[DepartmentWorkOrderResponse]


class ProgressProduct(PlanningModel):
    completed_quantity: str
    order_quantity: int
    task_quantity: int
    product_id: int
    factory_code: str
    product_name: str
    materials: list[ProgressMaterial]


class ProgressPlan(PlanningModel):
    production_plan_id: int
    order_no: str
    customer_name: str
    products: list[ProgressProduct]


class ProductionProgressEnvelope(PlanningModel):
    data: list[ProgressPlan]
    total: int


class DepartmentMovementCreate(PlanningModel):
    direction: Literal["receipt", "issue"]
    quantity: int = Field(strict=True, gt=0, le=9007199254740991)
    note: str = Field(default="", max_length=1000)
    request_id: UUID
    receipt_source: Literal["ticket", "warehouse"] | None = None
    ticket_id: int | None = Field(default=None, gt=0)
    warehouse_pick_id: int | None = Field(default=None, gt=0)
    input_material_node_id: str | None = Field(default=None, min_length=1, max_length=100)
    target_work_order_id: int | None = Field(default=None, gt=0)


class DepartmentMovementResponse(DepartmentMovementCreate):
    receipt_source: Literal["external", "ticket", "warehouse"] | None
    source_department: str | None
    target_department: str | None
    receipt_movement_ids: list[int]
    id: int
    actor_username: str
    created_at: str
    ticket_no: str | None
    material_no: str
    material_name: str


class HandoffChoice(PlanningModel):
    id: int
    label: str
    department_name: str


class HandoffOptionsResponse(PlanningModel):
    available_issue_quantity: str | None
    can_receive: bool
    targets: list[HandoffChoice]


class HandoffTicketResponse(PlanningModel):
    kind: Literal["normal", "rework", "return", "warehouse"]
    action: Literal["none", "receive", "inspect", "rework_receive", "rework_return"]
    can_receive: bool
    id: int
    ticket_no: str
    order_no: str
    factory_code: str
    product_name: str
    material_no: str
    material_name: str
    source_department: str
    target_department: str
    quantity: int
    received_quantity: str
    created_at: str
    note: str
    target_work_order_id: int | None
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


class SnapshotBomItemResponse(PlanningModel):
    id: int
    part_name: str
    part_no: str
    pcs: int
    remark: str
    sort_order: int


class PlanProductSnapshotResponse(PlanningModel):
    product_id: int
    source_version: int
    source_version_value: str
    product_name: str
    factory_code: str
    customer_code: str
    bom_items: list[SnapshotBomItemResponse]
    process_flow: ProcessFlowPayload


class PlanProductSnapshotEnvelope(PlanningModel):
    data: PlanProductSnapshotResponse
