"""Stable, persistence-free contract for QC destination routing."""

from dataclasses import dataclass
from typing import Any, Protocol

from domain.production_types import QcQualifiedDestination
from modules.organization.context_api import ProcedureContext
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)


@dataclass(frozen=True)
class QualifiedRouteResult:
    target_flow_node_id: str
    target_department_id: int


@dataclass(frozen=True)
class ReworkRouteResult:
    target_department_id: int


class QcRoutingStrategy(Protocol):
    def validate_context(
        self,
        session: Any,
        order: WorkOrderContext,
        procedure: ProcedureContext | None,
    ) -> None: ...

    def route_qualified(
        self,
        session: Any,
        *,
        order: WorkOrderContext,
        batch: InspectionBatchContext,
        production_item: ProductionItemContext,
        procedure: ProcedureContext | None,
        context: Any,
        node: dict,
        quantity: int,
        destination: QcQualifiedDestination,
    ) -> QualifiedRouteResult: ...

    def route_rework(
        self,
        session: Any,
        *,
        order: WorkOrderContext,
        batch: InspectionBatchContext,
        production_item: ProductionItemContext,
        procedure: ProcedureContext | None,
        node: dict,
        quantity: int,
    ) -> ReworkRouteResult: ...


__all__ = [
    "QcRoutingStrategy",
    "QualifiedRouteResult",
    "ReworkRouteResult",
]
