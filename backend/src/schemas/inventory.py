from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from domain.warehouse import (
    WarehouseCode,
    WarehouseItemType,
    WarehouseName,
    WarehouseOperationSourceType,
    WarehouseOperationStatus,
    WarehouseOperationType,
    WarehouseUnit,
)

from schemas.common import (
    CustomerOrderStatus,
    FinishedInventoryTransactionType,
    FinishedInventoryTransactionSourceType,
)


class InventoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WarehouseStockResponse(InventoryModel):
    id: int
    item_code: str
    item_name: str
    product_version: int
    item_type: WarehouseItemType
    specification: str
    inventory_unit: WarehouseUnit
    warehouse_code: WarehouseCode
    warehouse_name: WarehouseName
    quantity: int
    completion_status: str
    last_inbound_date: date | None
    last_outbound_date: date | None


class WarehouseStockEnvelope(InventoryModel):
    data: list[WarehouseStockResponse]


class WarehouseOperationResponse(InventoryModel):
    id: int
    operation_group_no: str
    operation_no: str
    operation_type: WarehouseOperationType
    source_type: WarehouseOperationSourceType
    production_plan_id: int | None
    production_plan_item_id: int | None
    work_order_id: int | None
    work_order_batch_id: int | None
    production_item_id: int | None
    warehouse_stock_id: int | None
    item_code: str
    item_name: str
    product_version: int
    item_type: WarehouseItemType
    specification: str
    inventory_unit: WarehouseUnit
    warehouse_code: WarehouseCode
    warehouse_name: WarehouseName
    completion_status: str
    quantity: int
    quantity_before: int | None
    quantity_after: int | None
    status: WarehouseOperationStatus
    actor_username: str
    error_message: str | None
    created_at: datetime
    executed_at: datetime | None
    manual_reviewed_at: datetime | None
    manual_reviewed_by: str | None
    manual_review_note: str | None
    can_review: bool


class WarehouseOperationEnvelope(InventoryModel):
    data: list[WarehouseOperationResponse]


class WarehouseOperationReviewInput(InventoryModel):
    operation_group_no: str = Field(min_length=1)
    review_note: str = Field(min_length=1)


class FinishedInventoryStockResponse(InventoryModel):
    id: int
    product_id: int
    product_version: int
    flow_node_id: str
    completed_flow_node_id: str
    completed_node_label: str
    item_code: str
    item_name: str
    quantity: int
    available_quantity: int
    revision: int


class FinishedInventoryStockEnvelope(InventoryModel):
    data: list[FinishedInventoryStockResponse]


class FinishedInventoryTransactionResponse(InventoryModel):
    id: int
    source_type: FinishedInventoryTransactionSourceType
    source_id: int
    finished_inventory_stock_id: int | None
    production_plan_id: int | None
    transaction_type: FinishedInventoryTransactionType
    quantity: int
    quantity_before: int
    quantity_after: int
    actor_username: str
    reason: str
    created_at: str
    item_code: str = ""
    item_name: str = ""
    customer_order_no: str = ""
    completed_node_label: str = ""


class FinishedInventoryTransactionEnvelope(InventoryModel):
    data: list[FinishedInventoryTransactionResponse]


class FinishedOrderStockResponse(InventoryModel):
    customer_order_id: int
    customer_order_no: str
    order_status: CustomerOrderStatus
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
