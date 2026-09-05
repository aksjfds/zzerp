"""Stable warehouse vocabulary shared across application boundaries."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, TypeAlias


WAREHOUSE_CODE_MAIN = "C01"
WAREHOUSE_CODE_AUXILIARY = "C02"
WAREHOUSE_NAME_MAIN = "主料仓"
WAREHOUSE_NAME_AUXILIARY = "辅料仓"
WAREHOUSE_UNIT_PCS = "PCS"

WAREHOUSE_OPERATION_INBOUND = "inbound"
WAREHOUSE_OPERATION_OUTBOUND = "outbound"

WAREHOUSE_OPERATION_PENDING = "pending"
WAREHOUSE_OPERATION_SUCCEEDED = "succeeded"
WAREHOUSE_OPERATION_FAILED = "failed"
WAREHOUSE_OPERATION_UNCERTAIN = "uncertain"

WAREHOUSE_SOURCE_PLAN_CONFIRMATION = "plan_confirmation"
WAREHOUSE_SOURCE_QC_INVENTORY = "qc_inventory"
WAREHOUSE_SOURCE_PRODUCTION_POSITION = "production_position"
WAREHOUSE_SOURCE_REVERSAL = "reversal"

WarehouseItemType: TypeAlias = Literal["part", "assembly"]
WarehouseCode: TypeAlias = Literal["C01", "C02"]
WarehouseName: TypeAlias = Literal["主料仓", "辅料仓"]
WarehouseUnit: TypeAlias = Literal["PCS"]
WarehouseOperationType: TypeAlias = Literal["inbound", "outbound"]
WarehouseOperationStatus: TypeAlias = Literal[
    "pending",
    "succeeded",
    "failed",
    "uncertain",
]
WarehouseOperationSourceType: TypeAlias = Literal[
    "plan_confirmation",
    "qc_inventory",
    "production_position",
    "reversal",
]


@dataclass(frozen=True, slots=True)
class WarehouseStockIdentity:
    """Business identity used by both the simulation table and SQL Server gateway."""

    item_code: str
    product_version: int
    item_type: WarehouseItemType
    completion_status: str
    warehouse_code: WarehouseCode


@dataclass(frozen=True, slots=True)
class WarehouseMaterialIdentity:
    item_code: str
    product_version: int
    item_type: WarehouseItemType


@dataclass(frozen=True, slots=True)
class WarehouseStockSnapshot:
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


@dataclass(frozen=True, slots=True)
class WarehouseOperationContext:
    source_type: WarehouseOperationSourceType
    production_plan_id: int | None = None
    production_plan_item_id: int | None = None
    work_order_id: int | None = None
    work_order_batch_id: int | None = None
    production_item_id: int | None = None


@dataclass(frozen=True, slots=True)
class WarehouseOperationSnapshot:
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


@dataclass(frozen=True, slots=True)
class WarehouseMutationResult:
    operation_group_no: str
    status: WarehouseOperationStatus
    requested_quantity: int
    processed_quantity: int
    operations: tuple[WarehouseOperationSnapshot, ...]
    error_message: str | None


__all__ = [
    "WAREHOUSE_CODE_AUXILIARY",
    "WAREHOUSE_CODE_MAIN",
    "WAREHOUSE_NAME_AUXILIARY",
    "WAREHOUSE_NAME_MAIN",
    "WAREHOUSE_OPERATION_FAILED",
    "WAREHOUSE_OPERATION_INBOUND",
    "WAREHOUSE_OPERATION_OUTBOUND",
    "WAREHOUSE_OPERATION_PENDING",
    "WAREHOUSE_OPERATION_SUCCEEDED",
    "WAREHOUSE_OPERATION_UNCERTAIN",
    "WAREHOUSE_SOURCE_PLAN_CONFIRMATION",
    "WAREHOUSE_SOURCE_PRODUCTION_POSITION",
    "WAREHOUSE_SOURCE_QC_INVENTORY",
    "WAREHOUSE_SOURCE_REVERSAL",
    "WAREHOUSE_UNIT_PCS",
    "WarehouseCode",
    "WarehouseItemType",
    "WarehouseName",
    "WarehouseMutationResult",
    "WarehouseOperationContext",
    "WarehouseOperationSnapshot",
    "WarehouseOperationSourceType",
    "WarehouseOperationStatus",
    "WarehouseOperationType",
    "WarehouseStockIdentity",
    "WarehouseMaterialIdentity",
    "WarehouseStockSnapshot",
    "WarehouseUnit",
]
