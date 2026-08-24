from datetime import date
from typing import Literal

from pydantic import Field

from schemas.common import FlowNodeType
from schemas.organization import ProcedureResponse
from schemas.production_base import ProductionModel


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
    node_type: FlowNodeType
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
        "unprocessed", "processing", "processing_completed", "qc", "rework", "completed"
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
