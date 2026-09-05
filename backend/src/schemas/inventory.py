from datetime import date, datetime
from typing import Literal

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

from schemas.common import CustomerOrderStatus


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
    processing_state_id: int
    reversal_of_operation_id: int | None
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


class WarehouseOperationReversalInput(InventoryModel):
    operation_group_no: str = Field(min_length=1)


class FinishedReceiptResponse(InventoryModel):
    id: int
    work_order_batch_id: int | None
    work_order_id: int | None
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    quantity: int
    status: Literal["pending", "received", "cancelled", "reversed"]
    received_at: datetime | None
    received_by: str | None
    corrected_at: datetime | None
    corrected_by: str | None
    correction_reason: str | None
    created_at: datetime
    revision: int


class FinishedReceiptEnvelope(InventoryModel):
    data: list[FinishedReceiptResponse]


class FinishedReceiptItemEnvelope(InventoryModel):
    data: FinishedReceiptResponse


class PendingFinishedReceiptResponse(InventoryModel):
    id: int
    work_order_batch_id: int | None
    work_order_id: int | None
    quantity: int
    created_at: datetime


class FinishedInboundItemResponse(InventoryModel):
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    planned_quantity: int
    production_plan_count: int
    arrived_quantity: int
    pending_receipts: list[PendingFinishedReceiptResponse]
    updated_at: datetime


class FinishedInboundItemEnvelope(InventoryModel):
    data: list[FinishedInboundItemResponse]
    total: int
    page: int
    page_size: int


class FinishedStockResponse(InventoryModel):
    id: int
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    revision: int
    updated_at: datetime


class FinishedStockEnvelope(InventoryModel):
    data: list[FinishedStockResponse]


class FinishedStockReservationResponse(InventoryModel):
    id: int
    finished_stock_id: int
    production_plan_id: int
    production_plan_item_id: int
    customer_order_id: int
    customer_order_no: str
    customer_order_item_id: int
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    reserved_quantity: int
    shipped_quantity: int
    released_quantity: int
    open_quantity: int
    created_at: datetime
    updated_at: datetime


class FinishedStockReservationEnvelope(InventoryModel):
    data: list[FinishedStockReservationResponse]


class FinishedStockTransactionResponse(InventoryModel):
    id: int
    finished_stock_id: int
    finished_receipt_id: int | None
    finished_stock_reservation_id: int | None
    operation_group_no: str
    reversal_of_transaction_id: int | None
    customer_order_id: int | None
    customer_order_no: str
    customer_order_item_id: int | None
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    transaction_type: Literal[
        "receipt",
        "receipt_reversal",
        "customer_shipment",
        "customer_shipment_reversal",
    ]
    quantity: int
    quantity_before: int
    quantity_after: int
    actor_username: str
    reason: str
    created_at: datetime


class FinishedStockTransactionEnvelope(InventoryModel):
    data: list[FinishedStockTransactionResponse]


class FinishedShipmentCandidateResponse(InventoryModel):
    customer_order_id: int
    customer_order_no: str
    order_status: CustomerOrderStatus
    customer_order_item_id: int
    item_code: str
    item_name: str
    product_version: int
    required_quantity: int
    reserved_quantity: int
    unreserved_quantity: int
    available_quantity: int
    shipped_quantity: int
    outstanding_quantity: int


class FinishedShipmentCandidateEnvelope(InventoryModel):
    data: list[FinishedShipmentCandidateResponse]


class FinishedShipmentCandidateItemEnvelope(InventoryModel):
    data: FinishedShipmentCandidateResponse


class FinishedShipmentInput(InventoryModel):
    quantity: int = Field(gt=0)


class OperationCorrectionInput(InventoryModel):
    reason: str | None = Field(default=None, max_length=1000)
