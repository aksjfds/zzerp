from datetime import date

from pydantic import BaseModel, ConfigDict, Field


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


class CustomerOrderProductProgress(SalesModel):
    customer_order_item_id: int
    product_id: int
    product_name: str
    factory_code: str
    total_quantity: int
    completed_quantity: int
    scrap_quantity: int
    lost_quantity: int
    unfinished_quantity: int
    po_shortage_quantity: int


class CustomerOrderResponse(SalesModel):
    id: int
    customer_order_no: str
    customer_id: int
    customer_name: str
    status: str
    revision: int
    remark: str
    items: list[CustomerOrderItemResponse]
    product_progress: list[CustomerOrderProductProgress] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CustomerOrderEnvelope(SalesModel):
    data: CustomerOrderResponse


class CustomerOrderListEnvelope(SalesModel):
    data: list[CustomerOrderResponse]
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
    item_type: str
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


class ProductionPlanInventoryItem(SalesModel):
    id: int
    customer_order_item_id: int
    item_type: str
    product_id: int
    product_version: int
    product_bom_id: int | None
    flow_node_id: str
    item_code: str
    item_name: str
    current_inventory_quantity: int
    reserved_inventory_quantity: int
    issued_inventory_quantity: int


class ProductionPlanResponse(SalesModel):
    id: int
    customer_order_id: int
    status: str
    revision: int
    product_summaries: list[ProductionPlanProductSummary]
    items: list[ProductionPlanItemResponse]
    inventory_items: list[ProductionPlanInventoryItem]
    confirmed_at: str | None
    confirmed_by: str | None
    created_at: str
    updated_at: str


class ProductionPlanEnvelope(SalesModel):
    data: ProductionPlanResponse
