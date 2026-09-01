from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from schemas.common import FlowNodeType
from schemas.organization import ProcedureResponse
from schemas.production_base import ProductionModel


class WorkbenchActivityResponse(ProductionModel):
    open_work_order_count: int = Field(ge=0)
    processing_work_order_count: int = Field(ge=0)
    ready_for_result_work_order_count: int = Field(ge=0)
    pending_qc_work_order_count: int = Field(ge=0)
    rework_work_order_count: int = Field(ge=0)


class WorkbenchInventorySourceResponse(ProductionModel):
    repository_id: int
    production_item_id: int
    source_work_order_id: int | None
    on_hand_quantity: int = Field(gt=0)
    reserved_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    arrived_at: str | None


class StandardWorkbenchSourceResponse(WorkbenchInventorySourceResponse):
    available_procedures: list[ProcedureResponse] = Field(default_factory=list)
    procedure_configuration_confirmed: bool
    can_create_work_order: bool


class WorkbenchPositionBase(ProductionModel):
    position_key: str
    position_type: str
    production_item_id: int | None
    customer_order_item_id: int
    customer_order_no: str
    customer_name: str
    product_id: int
    product_version: int
    factory_code: str
    product_name: str
    item_code: str
    item_name: str
    flow_node_id: str
    source_flow_node_id: str | None
    source_node_label: str | None
    node_type: FlowNodeType
    workshop_id: int
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    delivery_date: date
    arrived_at: str | None
    last_activity_at: str | None
    activity: WorkbenchActivityResponse
    can_create_work_order: bool


class StandardWorkbenchPositionResponse(WorkbenchPositionBase):
    position_type: Literal["standard"]
    production_item_id: int
    source_flow_node_id: str
    source_node_label: str
    on_hand_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    source_count: int = Field(ge=0)
    sources: list[StandardWorkbenchSourceResponse] = Field(default_factory=list)


class AssemblyWorkbenchInputMaterialResponse(ProductionModel):
    material_key: str
    item_code: str
    item_name: str
    unit_quantity: int = Field(gt=0)
    on_hand_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    allocated_quantity: int = Field(ge=0)
    sources: list[WorkbenchInventorySourceResponse] = Field(default_factory=list)


class AssemblyWorkbenchContinuationSourceResponse(WorkbenchInventorySourceResponse):
    available_procedures: list[ProcedureResponse] = Field(default_factory=list)
    procedure_configuration_confirmed: bool
    can_create_work_order: bool


class AssemblyWorkbenchPositionResponse(WorkbenchPositionBase):
    position_type: Literal["assembly"]
    source_flow_node_id: None = None
    source_node_label: None = None
    capacity_quantity: int = Field(ge=0)
    initial_capacity_quantity: int = Field(ge=0)
    continuation_capacity_quantity: int = Field(ge=0)
    input_materials_complete: bool
    can_create_initial_work_order: bool
    input_material_count: int = Field(ge=0)
    input_materials: list[AssemblyWorkbenchInputMaterialResponse] = Field(
        default_factory=list,
    )
    continuation_sources: list[AssemblyWorkbenchContinuationSourceResponse] = Field(
        default_factory=list,
    )
    available_procedures: list[ProcedureResponse] = Field(default_factory=list)
    procedure_configuration_confirmed: bool


ProductionWorkbenchPositionResponse = Annotated[
    StandardWorkbenchPositionResponse | AssemblyWorkbenchPositionResponse,
    Field(discriminator="position_type"),
]


class ProductionWorkbenchPositionListEnvelope(ProductionModel):
    data: list[ProductionWorkbenchPositionResponse]
    total: int = Field(ge=0)


__all__ = [
    "AssemblyWorkbenchInputMaterialResponse",
    "AssemblyWorkbenchContinuationSourceResponse",
    "AssemblyWorkbenchPositionResponse",
    "ProductionWorkbenchPositionListEnvelope",
    "ProductionWorkbenchPositionResponse",
    "StandardWorkbenchPositionResponse",
    "StandardWorkbenchSourceResponse",
    "WorkbenchActivityResponse",
    "WorkbenchInventorySourceResponse",
]
