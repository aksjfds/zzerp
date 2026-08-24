from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import (
    CustomerOrderStatus,
    FlowNodeType,
    ProductionItemType,
    ProductionPlanStatus,
)
from schemas.engineering import ProcessFlowPayload


class SalesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerOrderItemInput(SalesModel):
    id: int | None = Field(default=None, gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    delivery_date: date
    remark: str | None = Field(default=None, max_length=1000)


class CustomerOrderCreate(SalesModel):
    customer_order_no: str = Field(min_length=1, max_length=200)
    customer_id: int = Field(gt=0)
    remark: str | None = Field(default=None, max_length=1000)
    items: list[CustomerOrderItemInput] = Field(min_length=1, max_length=1000)


class CustomerOrderUpdate(CustomerOrderCreate):
    expected_revision: int = Field(gt=0)
    customer_order_no: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: int | None = Field(default=None, gt=0)


class CustomerOrderItemResponse(SalesModel):
    id: int
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    quantity: int
    delivery_date: date
    remark: str


class CustomerOrderResponse(SalesModel):
    id: int
    customer_order_no: str
    customer_id: int
    customer_name: str
    status: CustomerOrderStatus
    production_plan_status: ProductionPlanStatus | None = None
    can_edit: bool
    revision: int
    remark: str
    items: list[CustomerOrderItemResponse]
    created_at: str
    updated_at: str


class CustomerOrderEnvelope(SalesModel):
    data: CustomerOrderResponse


class CustomerOrderListEnvelope(SalesModel):
    data: list[CustomerOrderResponse]
    total: int


class CustomerOrderProgressDetail(SalesModel):
    customer_order_id: int
    customer_order_item_id: int
    factory_code: str
    product_name: str
    order_date: date
    customer_order_no: str
    customer_code: str
    order_quantity: int
    task_quantity: int
    shipped_quantity: int
    outstanding_quantity: int
    delivery_date: date
    remark: str


class CustomerOrderProgressDetailEnvelope(SalesModel):
    data: list[CustomerOrderProgressDetail]
    total: int


class ProductionPlanQuantityInput(SalesModel):
    id: int = Field(gt=0)
    planned_production_quantity: int = Field(ge=0)


class ProductionPlanUpdate(SalesModel):
    expected_revision: int = Field(gt=0)
    items: list[ProductionPlanQuantityInput] = Field(min_length=1, max_length=5000)


class ProductionPlanItemResponse(SalesModel):
    id: int
    customer_order_item_id: int
    item_type: ProductionItemType
    product_id: int
    product_version: int
    product_bom_id: int | None
    flow_node_id: str
    item_code: str
    item_name: str
    unit_requirement: int
    gross_required_quantity: int
    estimated_inventory_quantity: int
    available_inventory_quantity: int
    net_required_quantity: int
    planned_production_quantity: int
    reserved_inventory_quantity: int
    issued_inventory_quantity: int


class ProductionPlanProductSummary(SalesModel):
    customer_order_item_id: int
    product_id: int
    product_version: int
    product_code: str
    product_name: str
    order_quantity: int
    planned_finished_quantity: int


class ProductionPlanInventoryPartEquivalent(SalesModel):
    product_bom_id: int
    item_code: str
    item_name: str
    quantity: int


class ProductionPlanInventoryDecomposition(SalesModel):
    finished_equivalent_quantity: int
    parts: list[ProductionPlanInventoryPartEquivalent]


class ProductionPlanInventoryItem(SalesModel):
    id: int
    customer_order_item_id: int
    item_type: ProductionItemType
    product_id: int
    product_version: int
    product_bom_id: int | None
    flow_node_id: str
    item_code: str
    item_name: str
    completed_node_label: str
    current_inventory_quantity: int
    reserved_inventory_quantity: int
    issued_inventory_quantity: int
    decomposition: ProductionPlanInventoryDecomposition


class ProductionPlanResponse(SalesModel):
    id: int
    customer_order_id: int
    status: ProductionPlanStatus
    revision: int
    product_summaries: list[ProductionPlanProductSummary]
    items: list[ProductionPlanItemResponse]
    inventory_items: list[ProductionPlanInventoryItem]
    confirmed_at: str | None
    confirmed_by: str | None
    completed_at: str | None
    completed_by: str | None
    created_at: str
    updated_at: str


class ProductionPlanEnvelope(SalesModel):
    data: ProductionPlanResponse


class ProductionNodeStat(SalesModel):
    flow_node_id: str
    node_type: FlowNodeType
    current_quantity: int
    entered_quantity: int
    transferred_quantity: int
    abnormal_quantity: int
    output_quantity: int
    input_details: dict[str, int]


class ProductionEdgeStat(SalesModel):
    flow_edge_id: str
    transferred_quantity: int


class CustomerOrderProductProduction(SalesModel):
    customer_order_item_id: int
    product_name: str
    factory_code: str
    product_version: int
    order_quantity: int
    process_flow: ProcessFlowPayload
    node_stats: list[ProductionNodeStat]
    edge_stats: list[ProductionEdgeStat]


class CustomerOrderProductionResponse(SalesModel):
    customer_order_id: int
    status: CustomerOrderStatus
    products: list[CustomerOrderProductProduction]


class CustomerOrderProductionEnvelope(SalesModel):
    data: CustomerOrderProductionResponse
