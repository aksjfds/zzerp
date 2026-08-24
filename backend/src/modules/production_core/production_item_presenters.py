from __future__ import annotations

"""Stable material identity and display-name mapping."""

from sqlalchemy import select
from domain.production_types import WORK_ORDER_ASSEMBLY
from modules.production_core.persistence import ProductionItem, WorkOrder, WorkOrderMaterial
from modules.production_core.flow import load_production_flow
from modules.production_core.work_order_presenter_context import ProductionItemDisplayContext

def item_display(
    session,
    production_item: ProductionItem,
    context: ProductionItemDisplayContext | None = None,
) -> tuple[str, str]:
    return load_production_flow(
        session,
        production_item,
        flow_cache=context.flow_cache if context else None,
        order_items=context.order_items if context else None,
        bom_items=context.bom_items if context else None,
    ).item_name(production_item)

def production_item_name(
    session,
    production_item: ProductionItem,
    visited: set[int],
    context: ProductionItemDisplayContext | None = None,
) -> str:
    if production_item.id in visited:
        return item_display(session, production_item, context)[1]
    flow_context = load_production_flow(
        session,
        production_item,
        flow_cache=context.flow_cache if context else None,
        order_items=context.order_items if context else None,
        bom_items=context.bom_items if context else None,
    )
    if flow_context.bom_item is not None:
        return flow_context.bom_item.part_name
    source_order = (
        context.source_orders.get(production_item.id)
        if context is not None else None
    )
    if source_order is None and not (
        context is not None
        and production_item.id in context.source_order_item_ids_complete
    ):
        source_order = session.scalar(
            select(WorkOrder)
            .where(
                WorkOrder.production_item_id == production_item.id,
                WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
            )
            .order_by(WorkOrder.id.desc())
            .limit(1)
        )
    if context is not None and source_order is not None:
        context.source_orders[production_item.id] = source_order
    if context is not None:
        context.source_order_item_ids_complete.add(production_item.id)
    if source_order is not None:
        return assembly_output_name(
            session,
            source_order,
            visited | {production_item.id},
            context,
        )
    return flow_context.item_name(production_item)[1]

def production_item_sort_order(
    session,
    production_item: ProductionItem,
    visited: set[int],
    context: ProductionItemDisplayContext | None = None,
) -> int:
    if production_item.id in visited:
        return 2**31 - 1
    flow_context = load_production_flow(
        session,
        production_item,
        flow_cache=context.flow_cache if context else None,
        order_items=context.order_items if context else None,
        bom_items=context.bom_items if context else None,
    )
    if flow_context.bom_item is not None:
        return flow_context.bom_item.sort_order
    source_order = (
        context.source_orders.get(production_item.id)
        if context is not None else None
    )
    if source_order is None and not (
        context is not None
        and production_item.id in context.source_order_item_ids_complete
    ):
        source_order = session.scalar(
            select(WorkOrder)
            .where(
                WorkOrder.production_item_id == production_item.id,
                WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
            )
            .order_by(WorkOrder.id.desc())
            .limit(1)
        )
    if context is not None and source_order is not None:
        context.source_orders[production_item.id] = source_order
    if context is not None:
        context.source_order_item_ids_complete.add(production_item.id)
    if source_order is None:
        return 2**31 - 1
    source_ids = (
        context.material_item_ids.get(source_order.id, [])
        if context is not None
        and source_order.id in context.material_order_ids_complete
        else session.scalars(
            select(WorkOrderMaterial.production_item_id).where(
                WorkOrderMaterial.work_order_id == source_order.id
            )
        ).all()
    )
    if context is not None:
        context.material_item_ids[source_order.id] = list(source_ids)
        context.material_order_ids_complete.add(source_order.id)
    orders = [
        production_item_sort_order(
            session, item, visited | {production_item.id}, context
        )
        for item_id in source_ids
        if (
            item := (
                context.production_items.get(item_id)
                if context is not None else None
            ) or session.get(ProductionItem, item_id)
        ) is not None
    ]
    return min(orders, default=2**31 - 1)

def assembly_output_name(
    session,
    order: WorkOrder,
    visited: set[int] | None = None,
    context: ProductionItemDisplayContext | None = None,
) -> str:
    visited = visited or set()
    material_item_ids = (
        context.material_item_ids.get(order.id, [])
        if context is not None and order.id in context.material_order_ids_complete
        else session.scalars(
            select(WorkOrderMaterial.production_item_id)
            .where(WorkOrderMaterial.work_order_id == order.id)
            .order_by(WorkOrderMaterial.id)
        ).all()
    )
    if context is not None:
        context.material_item_ids[order.id] = list(material_item_ids)
        context.material_order_ids_complete.add(order.id)
    production_items = [
        item
        for item_id in material_item_ids
        if (
            item := (
                context.production_items.get(item_id)
                if context is not None else None
            ) or session.get(ProductionItem, item_id)
        ) is not None
    ]
    production_items.sort(
        key=lambda item: (
            production_item_sort_order(session, item, visited, context),
            item.id,
        )
    )
    names: list[str] = []
    for production_item in production_items:
        name = production_item_name(session, production_item, visited, context)
        base_name = name.removesuffix("装配体")
        if base_name and base_name not in names:
            names.append(base_name)
    if names:
        return f"{'-'.join(names)}装配体"
    flow_context = load_production_flow(
        session,
        (
            context.production_items.get(order.production_item_id)
            if context is not None else None
        ) or session.get(ProductionItem, order.production_item_id),
        flow_cache=context.flow_cache if context else None,
        order_items=context.order_items if context else None,
        bom_items=context.bom_items if context else None,
    )
    assembly_node = flow_context.nodes.get(order.flow_node_id, {})
    return assembly_node.get("output_name") or assembly_node.get("label") or "装配体"
