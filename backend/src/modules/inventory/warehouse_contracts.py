"""Typed requests and gateway factory contract for temporary warehouse operations."""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from domain.warehouse import WarehouseItemType, WarehouseOperationContext
from modules.inventory.warehouse_gateway import WarehouseGateway


WarehouseGatewayFactory = Callable[[Session], WarehouseGateway]


@dataclass(frozen=True, slots=True)
class WarehouseInboundRequest:
    operation_group_no: str
    context: WarehouseOperationContext
    item_code: str
    item_name: str
    product_version: int
    item_type: WarehouseItemType
    completion_status: str
    processing_state_id: int
    quantity: int
    actor_username: str
    specification: str = ""


@dataclass(frozen=True, slots=True)
class WarehouseOutboundRequest:
    operation_group_no: str
    context: WarehouseOperationContext
    item_code: str
    item_name: str
    product_version: int
    item_type: WarehouseItemType
    completion_status_priority: tuple[str, ...]
    processing_state_ids: tuple[tuple[str, int], ...]
    quantity: int
    actor_username: str
