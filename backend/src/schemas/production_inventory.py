from typing import Literal

from pydantic import Field

from schemas.production_base import ProductionModel


class ProductionPositionStorageInput(ProductionModel):
    production_item_id: int = Field(gt=0)
    flow_node_id: str = Field(min_length=1, max_length=200)
    source_flow_node_id: str = Field(min_length=1, max_length=200)
    position_version: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    quantity: int = Field(gt=0)


class ProductionPositionStorageResponse(ProductionModel):
    operation_group_no: str
    warehouse_stock_id: int
    quantity: int
    completion_status: str


class ProductionPositionStorageCandidate(ProductionModel):
    key: str
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
    completion_status: str
    available_quantity: int
    position_version: str


class ProductionPositionStorageListEnvelope(ProductionModel):
    data: list[ProductionPositionStorageCandidate]
