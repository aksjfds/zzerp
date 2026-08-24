from __future__ import annotations

"""Batch-loaded customer-order production context."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select, tuple_

from modules.engineering.model_api import Product, ProductBom
from modules.production_core.flow_api import load_product_flow
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.operational_api import ProductionItemDisplayContext
from modules.sales.model_api import CustomerOrderItem


@dataclass(slots=True)
class OrderProductionReadContext:
    session: object
    products: dict[int, Product]
    bom_items: dict[int, ProductBom]
    production_items_by_order_item: dict[int, list[ProductionItem]]
    repositories_by_item: dict[int, list[Repository]]
    movements_by_item: dict[int, list[ProductionMovement]]
    work_orders_by_item: dict[int, list[WorkOrder]]
    batches_by_order: dict[int, list[WorkOrderBatch]]
    display: ProductionItemDisplayContext


def _load_order_production_context(
    session,
    order_items: list[CustomerOrderItem],
) -> OrderProductionReadContext:
    product_ids = {item.product_id for item in order_items}
    products = {
        item.id: item
        for item in session.scalars(
            select(Product).where(Product.id.in_(product_ids))
        )
    } if product_ids else {}
    version_keys = {
        (item.product_id, item.product_version) for item in order_items
    }
    bom_items = list(session.scalars(
        select(ProductBom).where(
            tuple_(ProductBom.product_id, ProductBom.product_version).in_(
                version_keys
            )
        )
    )) if version_keys else []
    order_item_ids = {item.id for item in order_items}
    production_items = list(session.scalars(
        select(ProductionItem).where(
            ProductionItem.customer_order_item_id.in_(order_item_ids)
        )
    )) if order_item_ids else []
    production_item_ids = {item.id for item in production_items}
    repositories = list(session.scalars(
        select(Repository).where(
            Repository.production_item_id.in_(production_item_ids)
        )
    )) if production_item_ids else []
    movements = list(session.scalars(
        select(ProductionMovement).where(
            ProductionMovement.production_item_id.in_(production_item_ids)
        )
    )) if production_item_ids else []
    work_orders = list(session.scalars(
        select(WorkOrder).where(
            WorkOrder.production_item_id.in_(production_item_ids),
            WorkOrder.work_order_type.in_(("standard", "assembly")),
        )
    )) if production_item_ids else []
    work_order_ids = {item.id for item in work_orders}
    batches = list(session.scalars(
        select(WorkOrderBatch).where(
            WorkOrderBatch.work_order_id.in_(work_order_ids)
        )
    )) if work_order_ids else []
    material_item_ids: dict[int, list[int]] = defaultdict(list)
    if work_order_ids:
        for work_order_id, production_item_id in session.execute(
            select(
                WorkOrderMaterial.work_order_id,
                WorkOrderMaterial.production_item_id,
            ).where(WorkOrderMaterial.work_order_id.in_(work_order_ids))
        ):
            material_item_ids[work_order_id].append(production_item_id)
    source_orders: dict[int, WorkOrder] = {}
    for work_order in sorted(work_orders, key=lambda item: item.id, reverse=True):
        if work_order.work_order_type == "assembly":
            source_orders.setdefault(work_order.production_item_id, work_order)
    display = ProductionItemDisplayContext(
        production_items={item.id: item for item in production_items},
        source_orders=source_orders,
        material_item_ids=dict(material_item_ids),
        source_order_item_ids_complete=production_item_ids,
        material_order_ids_complete=work_order_ids,
        order_items={item.id: item for item in order_items},
        bom_items={item.id: item for item in bom_items},
    )
    for item in order_items:
        load_product_flow(
            session,
            item.product_id,
            item.product_version,
            display.flow_cache,
        )
    return OrderProductionReadContext(
        session=session,
        products=products,
        bom_items=display.bom_items,
        production_items_by_order_item=_group_by(
            production_items,
            "customer_order_item_id",
        ),
        repositories_by_item=_group_by(repositories, "production_item_id"),
        movements_by_item=_group_by(movements, "production_item_id"),
        work_orders_by_item=_group_by(work_orders, "production_item_id"),
        batches_by_order=_group_by(batches, "work_order_id"),
        display=display,
    )


def _group_by(items, attribute: str) -> dict[int, list]:
    grouped: dict[int, list] = defaultdict(list)
    for item in items:
        grouped[getattr(item, attribute)].append(item)
    return dict(grouped)
