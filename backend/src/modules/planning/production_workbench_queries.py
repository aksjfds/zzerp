"""Bulk data loading for the production-workbench read model."""

from datetime import datetime

from sqlalchemy import select, tuple_

from modules.engineering.model_api import Product, ProductBom, ProductProcessFlow
from modules.organization.model_api import Workshop
from modules.planning.persistence import ProductionPlan
from modules.planning.production_workbench_types import (
    AssemblyCandidate,
    CandidateView,
    DisplayData,
    StandardCandidate,
)
from modules.production_core.flow_api import load_production_flow
from modules.production_core.model_api import ProductionItem, ProductionMovement, Repository, WorkOrderBatch
from modules.production_core.operational_api import ProductionItemDisplayContext
from modules.sales.model_api import Customer, CustomerOrder, CustomerOrderItem


def _department_repositories(
    session,
    department_id: int,
    *,
    customer_order_item_id: int | None,
    production_item_id: int | None,
    flow_node_id: str | None,
) -> list[Repository]:
    statement = (
        select(Repository)
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionItem.customer_order_item_id,
        )
        .join(
            ProductionPlan,
            ProductionPlan.customer_order_id == CustomerOrderItem.customer_order_id,
        )
        .where(
            Repository.department_id == department_id,
            ProductionPlan.status.in_(("confirmed", "completed")),
        )
        .order_by(Repository.id)
    )
    if customer_order_item_id is not None:
        statement = statement.where(
            ProductionItem.customer_order_item_id == customer_order_item_id
        )
    if production_item_id is not None:
        statement = statement.where(
            Repository.production_item_id == production_item_id
        )
    if flow_node_id is not None:
        statement = statement.where(Repository.flow_node_id == flow_node_id)
    return list(session.scalars(statement))


def _load_display_data(
    session,
    item_ids: set[int],
    *,
    expand_order_items: bool,
) -> DisplayData:
    if not item_ids:
        return DisplayData({}, {}, {}, {}, {}, {})
    seed_items = list(session.scalars(
        select(ProductionItem).where(ProductionItem.id.in_(item_ids))
    ))
    order_item_ids = {item.customer_order_item_id for item in seed_items}
    items = seed_items
    if expand_order_items:
        items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id.in_(order_item_ids)
            )
        ))
    order_items = list(session.scalars(
        select(CustomerOrderItem).where(CustomerOrderItem.id.in_(order_item_ids))
    ))
    order_ids = {item.customer_order_id for item in order_items}
    orders = list(session.scalars(
        select(CustomerOrder).where(CustomerOrder.id.in_(order_ids))
    ))
    customers = list(session.scalars(
        select(Customer).where(Customer.id.in_({order.customer_id for order in orders}))
    ))
    product_ids = {item.product_id for item in items}
    products = list(session.scalars(
        select(Product).where(Product.id.in_(product_ids))
    ))
    bom_ids = {item.product_bom_id for item in items if item.product_bom_id is not None}
    boms = list(session.scalars(
        select(ProductBom).where(ProductBom.id.in_(bom_ids))
    )) if bom_ids else []
    version_keys = {(item.product_id, item.product_version) for item in items}
    flows = list(session.scalars(
        select(ProductProcessFlow).where(
            tuple_(
                ProductProcessFlow.product_id,
                ProductProcessFlow.product_version,
            ).in_(version_keys)
        )
    ))
    presentation = ProductionItemDisplayContext(
        production_items={item.id: item for item in items},
        order_items={item.id: item for item in order_items},
        bom_items={item.id: item for item in boms},
        flow_cache={(item.product_id, item.product_version): item for item in flows},
    )
    contexts = {
        item.id: load_production_flow(
            session,
            item,
            flow_cache=presentation.flow_cache,
            order_items=presentation.order_items,
            bom_items=presentation.bom_items,
        )
        for item in items
    }
    workshop_ids = {
        workshop_id
        for context in contexts.values()
        for node in context.nodes.values()
        if isinstance((workshop_id := node.get("workshop_id")), int)
    }
    workshops = list(session.scalars(
        select(Workshop).where(Workshop.id.in_(workshop_ids))
    )) if workshop_ids else []
    return DisplayData(
        items={item.id: item for item in items},
        orders={item.id: item for item in orders},
        customers={item.id: item for item in customers},
        products={item.id: item for item in products},
        contexts=contexts,
        workshops={item.id: item for item in workshops},
    )


def _arrival_times(
    session,
    selected: list[CandidateView],
    display: DisplayData,
    department_id: int,
) -> dict[tuple, datetime]:
    selected_standard = {
        view.candidate.key
        for view in selected
        if isinstance(view.candidate, StandardCandidate)
    }
    selected_assembly = {
        view.candidate.key
        for view in selected
        if isinstance(view.candidate, AssemblyCandidate)
    }
    item_ids = {
        repository.production_item_id
        for view in selected
        for repository in view.candidate.repositories
    }
    item_ids.update(
        item_id
        for view in selected
        for item_id in view.candidate.activity.production_item_ids
    )
    item_ids.update(
        allocation.production_item_id
        for view in selected
        if isinstance(view.candidate, AssemblyCandidate)
        for allocation in view.candidate.allocations
    )
    if not item_ids:
        return {}
    result: dict[tuple, datetime] = {}
    rows = session.execute(
        select(ProductionMovement, WorkOrderBatch.source_flow_node_id)
        .outerjoin(
            WorkOrderBatch,
            WorkOrderBatch.id == ProductionMovement.work_order_batch_id,
        )
        .where(
            ProductionMovement.target_department_id == department_id,
            ProductionMovement.production_item_id.in_(item_ids),
        )
    )
    for movement, batch_source_flow_node_id in rows:
        target_node_id = movement.target_flow_node_id
        if target_node_id is None:
            continue
        source_node_id = (
            batch_source_flow_node_id
            if movement.movement_type == "qc_rework"
            and batch_source_flow_node_id is not None
            else movement.source_flow_node_id
        )
        standard_key = (
            movement.production_item_id,
            target_node_id,
            source_node_id,
        )
        if source_node_id is not None and standard_key in selected_standard:
            _keep_latest(result, ("standard", *standard_key), movement.created_at)
        item = display.items.get(movement.production_item_id)
        if item is not None:
            assembly_key = (item.customer_order_item_id, target_node_id)
            if assembly_key in selected_assembly:
                _keep_latest(result, ("assembly", *assembly_key), movement.created_at)
    return result


def _keep_latest(result: dict, key: tuple, timestamp: datetime) -> None:
    if key not in result or result[key] < timestamp:
        result[key] = timestamp
