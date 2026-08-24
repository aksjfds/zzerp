from __future__ import annotations

"""Current repository-backed production cards."""

from datetime import date, datetime, time, timedelta
from sqlalchemy import and_, case, func, select
from domain.time import BUSINESS_TIMEZONE, business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Workshop
from modules.planning.persistence import ProductionPlan
from modules.production_core.model_api import ProductionItem, ProductionMovement, Repository, WorkOrderBatch
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.card_read_api import position_statuses, reserved_quantities
from modules.production_core.flow_api import load_production_flow
from modules.organization.read_api import get_procedure_views
from modules.production_core.operational_api import ProductionItemDisplayContext, production_item_name
from modules.planning.production_card_support import _material_source_name, _normal_input_material_keys, _normal_input_source_ids, _workshop_procedures
from domain.material_identity import production_item_material_key
from modules.planning.production_card_filters import source_keyword_filter

def _current_cards(
    session,
    department: Department,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
) -> list[dict]:
    arrival_source = case(
        (
            ProductionMovement.movement_type == "qc_rework",
            WorkOrderBatch.source_flow_node_id,
        ),
        else_=ProductionMovement.source_flow_node_id,
    )
    latest_arrivals = (
        select(
            ProductionMovement.production_item_id.label("production_item_id"),
            ProductionMovement.target_flow_node_id.label("flow_node_id"),
            arrival_source.label("source_flow_node_id"),
            func.max(ProductionMovement.created_at).label("arrived_at"),
        )
        .select_from(ProductionMovement)
        .outerjoin(
            WorkOrderBatch,
            WorkOrderBatch.id == ProductionMovement.work_order_batch_id,
        )
        .join(
            Repository,
            and_(
                Repository.production_item_id == ProductionMovement.production_item_id,
                Repository.flow_node_id == ProductionMovement.target_flow_node_id,
                Repository.source_flow_node_id == arrival_source,
                Repository.department_id == ProductionMovement.target_department_id,
            ),
        )
        .where(
            ProductionMovement.target_department_id == department.id,
            Repository.department_id == department.id,
        )
        .group_by(
            ProductionMovement.production_item_id,
            ProductionMovement.target_flow_node_id,
            arrival_source,
        )
        .subquery()
    )
    statement = (
        select(
            Repository,
            ProductionItem,
            CustomerOrderItem,
            CustomerOrder,
            Product,
            ProductBom,
            latest_arrivals.c.arrived_at,
        )
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
        .join(ProductionPlan, ProductionPlan.customer_order_id == CustomerOrder.id)
        .join(Product, Product.id == CustomerOrderItem.product_id)
        .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
        .outerjoin(
            latest_arrivals,
            and_(
                latest_arrivals.c.production_item_id == Repository.production_item_id,
                latest_arrivals.c.flow_node_id == Repository.flow_node_id,
                latest_arrivals.c.source_flow_node_id
                == Repository.source_flow_node_id,
            ),
        )
        .where(
            Repository.department_id == department.id,
            ProductionPlan.status == "confirmed",
        )
    )
    # Assembly filters are applied only after complete material groups are built.
    if department.department_code != "assembly":
        statement = _apply_current_source_filters(
            statement,
            latest_arrivals.c.arrived_at,
            keyword,
            arrived_from,
            arrived_to,
        )
    rows = session.execute(statement).all()
    repository_ids = [row.Repository.id for row in rows]
    reserved_by_id = reserved_quantities(session, repository_ids)
    positions = list(dict.fromkeys(
        (
            row.ProductionItem.id,
            row.Repository.flow_node_id,
            row.Repository.source_flow_node_id,
        )
        for row in rows
    ))
    arrived_by_position = {
        (
            row.ProductionItem.id,
            row.Repository.flow_node_id,
            row.Repository.source_flow_node_id,
        ): row.arrived_at
        for row in rows
    }
    status_by_position = position_statuses(
        session, department.id, department.department_code, positions
    )
    procedure_views = {}
    for item in get_procedure_views(session):
        procedure_views.setdefault(
            (item.workshop_id, item.procedure_type, item.input_mode), []
        ).append(item)
    display_context = ProductionItemDisplayContext(
        production_items={row.ProductionItem.id: row.ProductionItem for row in rows},
        order_items={row.CustomerOrderItem.id: row.CustomerOrderItem for row in rows},
        bom_items={
            row.ProductBom.id: row.ProductBom
            for row in rows
            if row.ProductBom is not None
        },
    )
    return [
        _current_card(
            session, row.Repository, row.ProductionItem, row.CustomerOrderItem,
            row.CustomerOrder, row.Product, row.ProductBom, department,
            reserved_by_id.get(row.Repository.id, 0),
            arrived_by_position.get((
                row.ProductionItem.id,
                row.Repository.flow_node_id,
                row.Repository.source_flow_node_id,
            )),
            status_by_position[(
                row.ProductionItem.id,
                row.Repository.flow_node_id,
                row.Repository.source_flow_node_id,
            )],
            procedure_views,
            display_context,
        )
        for row in rows
    ]

def _apply_current_source_filters(
    statement,
    arrival,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
):
    if arrived_from:
        statement = statement.where(
            arrival >= datetime.combine(arrived_from, time.min, BUSINESS_TIMEZONE)
        )
    if arrived_to:
        statement = statement.where(
            arrival < datetime.combine(
                arrived_to + timedelta(days=1), time.min, BUSINESS_TIMEZONE
            )
        )

    keyword_filter = source_keyword_filter(keyword)
    if keyword_filter is not None:
        statement = statement.where(keyword_filter)
    return statement


def _current_card(
    session, repository, production_item, order_item, order, product, bom_item,
    department, reserved, arrived_at, work_status, procedure_views,
    display_context,
) -> dict:
    context = load_production_flow(
        session,
        production_item,
        flow_cache=display_context.flow_cache,
        order_items=display_context.order_items,
        bom_items=display_context.bom_items,
    )
    node = context.nodes.get(repository.flow_node_id, {})
    source = context.nodes.get(repository.source_flow_node_id, {})
    workshop = (
        session.get(Workshop, node.get("workshop_id"))
        if node.get("workshop_id") else None
    )
    procedures = _workshop_procedures(
        procedure_views,
        workshop.id if workshop else None,
        (
            "purchase_receipt"
            if department.department_code == "purchasing"
            else "standard"
        ),
        "multiple" if node.get("type") == "assembly" else "single",
    )
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(
            session,
            production_item,
            set(),
            display_context,
        )
        part_no = part_name
    is_assembly_node = node.get("type") == "assembly"
    card = {
        "card_key": f"repository:{repository.id}",
        "repository_id": repository.id,
        "production_item_id": production_item.id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": bom_item.id if bom_item else None,
        "part_name": part_name,
        "part_no": part_no,
        "flow_node_id": repository.flow_node_id,
        "node_type": str(node.get("type") or ""),
        "source_flow_node_id": repository.source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "material_source_name": _material_source_name(context, production_item),
        "workshop_id": workshop.id if workshop else 0,
        "available_procedures": procedures,
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": repository.quantity,
        "available_quantity": max(repository.quantity - reserved, 0),
        "assembly_unit_quantity": bom_item.pcs if bom_item else int(
            context.nodes.get(production_item.origin_flow_node_id, {}).get("output_pcs", 1)
        ),
        "assembly_required_source_ids": [],
        "assembly_material_key": production_item_material_key(production_item),
        "assembly_required_material_keys": [],
        "assembly_group_complete": not is_assembly_node,
        "assembly_output_name": node.get("output_name") if is_assembly_node else None,
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(arrived_at),
        "work_status": work_status,
        "can_create_work_order": workshop is not None and reserved < repository.quantity,
    }
    if is_assembly_node:
        card["assembly_required_source_ids"] = _normal_input_source_ids(
            context.flow, repository.flow_node_id
        )
        card["assembly_required_material_keys"] = _normal_input_material_keys(
            context.flow, context.nodes, repository.flow_node_id
        )
    return card
