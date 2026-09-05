from typing import Literal

from pydantic import Field

from schemas.production_base import ProductionModel


class ProductionPositionStorageInput(ProductionModel):
    production_item_id: int = Field(gt=0)
    processing_state_id: int = Field(gt=0)
    flow_node_id: str = Field(min_length=1, max_length=200)
    source_flow_node_id: str = Field(min_length=1, max_length=200)
    position_version: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    quantity: int = Field(gt=0)


class ProductionPositionStorageResponse(ProductionModel):
    operation_group_no: str
    warehouse_stock_id: int
    quantity: int
    processing_status: str


class MaterialProcessingHistoryItem(ProductionModel):
    flow_node_id: str
    procedure_id: int | None
    procedure_name: str
    is_temporary: bool
    completion_result: Literal["none", "returned", "released", "stored"]


class DepartmentMaterialPosition(ProductionModel):
    key: str
    production_item_id: int
    processing_state_id: int
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
    resume_flow_node_id: str
    procedure_history: list[MaterialProcessingHistoryItem]
    qc_status: Literal["none", "returned", "released", "stored"]
    processing_status: str
    on_hand_quantity: int = Field(gt=0)
    occupied_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    position_version: str


class DepartmentMaterialPositionListEnvelope(ProductionModel):
    data: list[DepartmentMaterialPosition]
