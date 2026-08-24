from __future__ import annotations

"""Batch-loaded context for work-order presentation."""

from dataclasses import dataclass, field

from sqlalchemy import select

from domain.production_types import WORK_ORDER_ASSEMBLY
from modules.engineering.model_api import Product, ProductBom, ProductProcessFlow
from modules.organization.model_api import Procedure
from modules.production_core.flow import load_product_flow, load_production_flow
from modules.production_core.persistence import (
    ProductionItem,
    ProductionOperationUndo,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


@dataclass
class ProductionItemDisplayContext:
    production_items: dict[int, ProductionItem] = field(default_factory=dict)
    source_orders: dict[int, WorkOrder] = field(default_factory=dict)
    material_item_ids: dict[int, list[int]] = field(default_factory=dict)
    source_order_item_ids_complete: set[int] = field(default_factory=set)
    material_order_ids_complete: set[int] = field(default_factory=set)
    order_items: dict[int, CustomerOrderItem] = field(default_factory=dict)
    bom_items: dict[int, ProductBom] = field(default_factory=dict)
    flow_cache: dict[tuple[int, int], ProductProcessFlow] = field(default_factory=dict)


@dataclass
class WorkOrderPresenterContext:
    display: ProductionItemDisplayContext
    customer_orders: dict[int, CustomerOrder]
    products: dict[int, Product]
    procedures: dict[int, Procedure]
    batches: dict[int, list[WorkOrderBatch]]
    undo_operations: dict[int, object]


def build_work_order_presenter_context(
    session,
    orders: list[WorkOrder],
    *,
    batches: dict[int, list[WorkOrderBatch]] | None = None,
    material_item_ids: dict[int, list[int]] | None = None,
    undo_operations: dict[int, object] | None = None,
) -> WorkOrderPresenterContext:
    """Bulk-load context used while serializing a page of work orders."""
    order_ids = {order.id for order in orders}
    if batches is None:
        batches = {}
        loaded_batches = (
            session.scalars(
                select(WorkOrderBatch)
                .where(WorkOrderBatch.work_order_id.in_(order_ids))
                .order_by(WorkOrderBatch.id)
            )
            if order_ids
            else ()
        )
        for batch in loaded_batches:
            batches.setdefault(batch.work_order_id, []).append(batch)
    if material_item_ids is None:
        material_item_ids = {}
        loaded_materials = (
            session.execute(
                select(
                    WorkOrderMaterial.work_order_id,
                    WorkOrderMaterial.production_item_id,
                ).where(WorkOrderMaterial.work_order_id.in_(order_ids))
            )
            if order_ids
            else ()
        )
        for work_order_id, production_item_id in loaded_materials:
            material_item_ids.setdefault(work_order_id, []).append(
                production_item_id
            )
    if undo_operations is None:
        undo_operations = {}
        loaded_undo_operations = (
            session.scalars(
                select(ProductionOperationUndo)
                .where(
                    ProductionOperationUndo.work_order_id.in_(order_ids),
                    ProductionOperationUndo.status == "applied",
                )
                .order_by(
                    ProductionOperationUndo.work_order_id,
                    ProductionOperationUndo.id.desc(),
                )
            )
            if order_ids
            else ()
        )
        for operation in loaded_undo_operations:
            undo_operations.setdefault(operation.work_order_id, operation)
    production_item_ids = {order.production_item_id for order in orders}
    production_item_ids.update(
        production_item_id
        for item_ids in material_item_ids.values()
        for production_item_id in item_ids
    )
    production_items = list(
        session.scalars(
            select(ProductionItem).where(
                ProductionItem.id.in_(production_item_ids)
            )
        )
    )
    order_item_ids = {
        item.customer_order_item_id for item in production_items
    }
    order_items = list(
        session.scalars(
            select(CustomerOrderItem).where(
                CustomerOrderItem.id.in_(order_item_ids)
            )
        )
    ) if order_item_ids else []
    customer_order_ids = {item.customer_order_id for item in order_items}
    customer_orders = (
        list(
            session.scalars(
                select(CustomerOrder).where(
                    CustomerOrder.id.in_(customer_order_ids)
                )
            )
        )
        if customer_order_ids
        else []
    )
    product_ids = {item.product_id for item in production_items}
    products = (
        list(
            session.scalars(
                select(Product).where(Product.id.in_(product_ids))
            )
        )
        if product_ids
        else []
    )
    bom_ids = {
        item.product_bom_id
        for item in production_items
        if item.product_bom_id is not None
    }
    bom_items = (
        list(
            session.scalars(
                select(ProductBom).where(ProductBom.id.in_(bom_ids))
            )
        )
        if bom_ids
        else []
    )
    procedure_ids = {order.procedure_id for order in orders}
    procedures = (
        list(
            session.scalars(
                select(Procedure).where(Procedure.id.in_(procedure_ids))
            )
        )
        if procedure_ids
        else []
    )
    production_item_by_id = {item.id: item for item in production_items}
    order_item_by_id = {item.id: item for item in order_items}
    bom_item_by_id = {item.id: item for item in bom_items}
    flow_cache: dict[tuple[int, int], ProductProcessFlow] = {}
    for order_item in order_items:
        load_product_flow(
            session,
            order_item.product_id,
            order_item.product_version,
            flow_cache,
        )
    source_orders: dict[int, WorkOrder] = {}
    if production_item_ids:
        for source_order in session.scalars(
            select(WorkOrder)
            .where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
            )
            .order_by(WorkOrder.production_item_id, WorkOrder.id.desc())
        ):
            source_orders.setdefault(source_order.production_item_id, source_order)
    return WorkOrderPresenterContext(
        display=ProductionItemDisplayContext(
            production_items=production_item_by_id,
            source_orders=source_orders,
            material_item_ids=material_item_ids,
            source_order_item_ids_complete=set(production_item_ids),
            material_order_ids_complete={order.id for order in orders},
            order_items=order_item_by_id,
            bom_items=bom_item_by_id,
            flow_cache=flow_cache,
        ),
        customer_orders={item.id: item for item in customer_orders},
        products={item.id: item for item in products},
        procedures={item.id: item for item in procedures},
        batches=batches,
        undo_operations=undo_operations,
    )


def work_order_context(
    session,
    order: WorkOrder,
    context: WorkOrderPresenterContext | None = None,
):
    production_item = (
        context.display.production_items.get(order.production_item_id)
        if context is not None
        else session.get(ProductionItem, order.production_item_id)
    )
    flow_context = load_production_flow(
        session,
        production_item,
        flow_cache=context.display.flow_cache if context else None,
        order_items=context.display.order_items if context else None,
        bom_items=context.display.bom_items if context else None,
    )
    customer_order = (
        context.customer_orders.get(flow_context.order_item.customer_order_id)
        if context is not None
        else session.get(
            CustomerOrder,
            flow_context.order_item.customer_order_id,
        )
    )
    return customer_order, flow_context.bom_item, production_item, flow_context
