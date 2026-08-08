from pydantic import BaseModel, ConfigDict, Field


class InventoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryStockResponse(InventoryModel):
    id: int
    department_code: str
    item_type: str
    product_id: int
    product_version: int
    product_bom_id: int | None
    flow_node_id: str
    completed_flow_node_id: str
    completed_node_label: str
    item_code: str
    item_name: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    revision: int


class InventoryStockEnvelope(InventoryModel):
    data: list[InventoryStockResponse]


class InventoryTransactionResponse(InventoryModel):
    id: int
    inventory_stock_id: int
    production_plan_id: int | None
    transaction_type: str
    quantity: int
    quantity_before: int
    quantity_after: int
    reserved_before: int
    reserved_after: int
    actor_username: str
    reason: str
    created_at: str
    item_code: str = ""
    item_name: str = ""
    customer_order_no: str = ""
    completed_node_label: str = ""


class InventoryTransactionEnvelope(InventoryModel):
    data: list[InventoryTransactionResponse]


class InventoryIssueItemInput(InventoryModel):
    reservation_id: int = Field(gt=0)
    quantity: int = Field(ge=0)


class InventoryIssueInput(InventoryModel):
    department_code: str = Field(pattern="^(warehouse|finished)$")
    items: list[InventoryIssueItemInput] = Field(min_length=1, max_length=5000)


class InventoryOutboundItemResponse(InventoryModel):
    reservation_id: int
    item_code: str
    item_name: str
    reserved_quantity: int
    issued_quantity: int
    remaining_quantity: int
    completed_node_label: str


class InventoryOutboundPlanResponse(InventoryModel):
    production_plan_id: int
    customer_order_id: int
    customer_order_no: str
    department_code: str
    items: list[InventoryOutboundItemResponse]


class InventoryOutboundPlanEnvelope(InventoryModel):
    data: list[InventoryOutboundPlanResponse]


class FinishedOrderStockResponse(InventoryModel):
    customer_order_id: int
    customer_order_no: str
    order_status: str
    customer_order_item_id: int
    item_code: str
    item_name: str
    product_version: int
    required_quantity: int
    pending_quantity: int
    available_quantity: int
    shipped_quantity: int
    outstanding_quantity: int


class FinishedOrderStockEnvelope(InventoryModel):
    data: list[FinishedOrderStockResponse]


class FinishedOrderStockItemEnvelope(InventoryModel):
    data: FinishedOrderStockResponse


class FinishedShipmentInput(InventoryModel):
    quantity: int = Field(gt=0)
