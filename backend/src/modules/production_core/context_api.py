"""Stable structural contracts for production-core runtime context.

The concrete objects currently happen to be SQLAlchemy records. Collaborating
modules depend only on these fields so persistence classes remain private.
"""

from datetime import datetime
from typing import Protocol

from domain.production_types import QcQualifiedDestination


class InventorySourceContext(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def production_item_id(self) -> int: ...

    @property
    def flow_node_id(self) -> str: ...

    @property
    def source_flow_node_id(self) -> str: ...

    @property
    def department_id(self) -> int: ...

    @property
    def quantity(self) -> int: ...


class ProductionItemContext(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def customer_order_item_id(self) -> int: ...

    @property
    def product_id(self) -> int: ...

    @property
    def product_version(self) -> int: ...

    @property
    def origin_flow_node_id(self) -> str: ...

    @property
    def product_bom_id(self) -> int | None: ...


class WorkOrderContext(Protocol):
    id: int
    production_item_id: int
    procedure_id: int
    source_flow_node_id: str | None
    flow_node_id: str
    work_order_type: str
    created_by: str
    worker_name: str | None
    completed_quantity: int
    processed_quantity: int
    quantity: int
    status: str
    closed_at: datetime | None


class InspectionBatchContext(Protocol):
    id: int
    work_order_id: int
    source_flow_node_id: str
    rework_source_batch_id: int | None
    submitted_quantity: int
    rework_quantity: int | None
    qualified_quantity: int | None
    qualified_destination: QcQualifiedDestination | None
    destination_decided_at: datetime | None
    recorded_at: datetime | None


__all__ = [
    "InventorySourceContext",
    "InspectionBatchContext",
    "ProductionItemContext",
    "WorkOrderContext",
]
