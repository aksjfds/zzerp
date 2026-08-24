"""Stable presentation facade for production work orders."""

from modules.production_core.production_item_presenters import (
    assembly_output_name,
    item_display,
    production_item_name,
    production_item_sort_order,
)
from modules.production_core.work_order_presenter_context import (
    ProductionItemDisplayContext,
    WorkOrderPresenterContext,
    build_work_order_presenter_context,
    work_order_context,
)
from modules.production_core.work_order_serializers import (
    map_work_order,
    serialize_batch,
)


def serialize_work_order(
    session,
    order,
    context: WorkOrderPresenterContext | None = None,
) -> dict:
    presenter_context = context or build_work_order_presenter_context(
        session,
        [order],
    )
    return map_work_order(session, order, presenter_context)


__all__ = [
    "ProductionItemDisplayContext",
    "WorkOrderPresenterContext",
    "assembly_output_name",
    "build_work_order_presenter_context",
    "item_display",
    "production_item_name",
    "production_item_sort_order",
    "serialize_batch",
    "serialize_work_order",
    "work_order_context",
]
