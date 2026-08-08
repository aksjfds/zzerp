"""Stable structural contracts for production-core runtime context.

The concrete objects currently happen to be SQLAlchemy records. Collaborating
modules depend only on these fields so persistence classes remain private.
"""

from datetime import datetime
from typing import Protocol


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
    @property
    def id(self) -> int: ...

    @property
    def production_item_id(self) -> int: ...

    @property
    def procedure_id(self) -> int | None: ...

    @property
    def applied_tag_set_id(self) -> int | None: ...

    @property
    def source_flow_node_id(self) -> str: ...

    @property
    def flow_node_id(self) -> str: ...

    @property
    def source_tag_set_id(self) -> int | None: ...

    @property
    def target_tag_set_id(self) -> int | None: ...

    @property
    def work_order_type(self) -> str: ...

    @property
    def completed_quantity(self) -> int: ...

    @property
    def processed_quantity(self) -> int: ...

    @property
    def quantity(self) -> int: ...

    @property
    def status(self) -> str: ...

    @property
    def closed_at(self) -> datetime | None: ...


__all__ = [
    "InventorySourceContext",
    "ProductionItemContext",
    "WorkOrderContext",
]
