"""Stable structural contracts for quality-owned runtime context."""

from datetime import datetime
from typing import Protocol


class InspectionBatchContext(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def work_order_id(self) -> int: ...

    @property
    def source_flow_node_id(self) -> str: ...

    @property
    def rework_source_batch_id(self) -> int | None: ...

    @property
    def submitted_quantity(self) -> int: ...

    @property
    def rework_quantity(self) -> int | None: ...

    @property
    def recorded_at(self) -> datetime | None: ...


__all__ = ["InspectionBatchContext"]
