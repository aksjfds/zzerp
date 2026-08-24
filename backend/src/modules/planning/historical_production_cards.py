from __future__ import annotations

"""Historical work-order-backed production cards."""

from datetime import date, datetime, time, timedelta
from sqlalchemy import func, select, tuple_
from domain.time import BUSINESS_TIMEZONE, business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Procedure, Workshop
from modules.production_core.model_api import ProductionItem, ProductionMovement, WorkOrder, WorkOrderBatch, WorkOrderMaterial
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.card_read_api import work_order_stage
from modules.production_core.flow_api import load_production_flow
from modules.production_core.operational_api import ProductionItemDisplayContext, production_item_name
from modules.planning.production_card_filters import source_keyword_filter
from modules.planning.production_card_support import _material_source_name, _normal_input_material_keys, _normal_input_source_ids
from domain.material_identity import production_item_material_key

def _historical_cards(
    session,
    department,
    current_positions,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
) -> list[dict]:
    if department.department_code == "assembly":
        candidates = session.execute(
            select(
                WorkOrderMaterial.production_item_id,
                WorkOrder.flow_node_id,
            )
            .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
            .where(
                WorkOrder.work_order_type == "assembly",
                WorkOrder.status.in_(("open", "closed")),
            )
            .distinct()
        ).all()
    else:
        candidates = session.execute(
            select(
                WorkOrder.production_item_id,
                WorkOrder.flow_node_id,
                WorkOrder.source_flow_node_id,
            )
            .join(Procedure, Procedure.id == WorkOrder.procedure_id)
            .join(Workshop, Workshop.id == Procedure.workshop_id)
            .where(
                Workshop.department_id == department.id,
                WorkOrder.status == "closed",
                WorkOrder.source_flow_node_id.is_not(None),
            )
            .distinct()
        ).all()
    candidate_positions = list(candidates)
    apply_member_filters = department.department_code != "assembly"
    keyword_filter = source_keyword_filter(keyword) if apply_member_filters else None
    if candidate_positions and keyword_filter is not None:
        candidate_item_ids = {item[0] for item in candidate_positions}
        matching_item_ids = set(
            session.scalars(
                select(ProductionItem.id)
                .join(
                    CustomerOrderItem,
                    CustomerOrderItem.id == ProductionItem.customer_order_item_id,
                )
                .join(Product, Product.id == CustomerOrderItem.product_id)
                .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
                .where(
                    ProductionItem.id.in_(candidate_item_ids),
                    keyword_filter,
                )
            )
        )
        candidate_positions = [
            position
            for position in candidate_positions
            if position[0] in matching_item_ids
        ]
    ranked_movements = None
    if candidate_positions:
        if department.department_code == "assembly":
            ranked_movements = (
                select(
                    ProductionMovement.id.label("movement_id"),
                    ProductionMovement.production_item_id,
                    ProductionMovement.target_flow_node_id,
                    ProductionMovement.created_at.label("movement_created_at"),
                    func.row_number().over(
                        partition_by=(
                            ProductionMovement.production_item_id,
                            ProductionMovement.target_flow_node_id,
                        ),
                        order_by=(
                            ProductionMovement.created_at.desc(),
                            ProductionMovement.id.desc(),
                        ),
                    ).label("position_rank"),
                )
                .where(
                    ProductionMovement.target_department_id == department.id,
                    tuple_(
                        ProductionMovement.production_item_id,
                        ProductionMovement.target_flow_node_id,
                    ).in_(candidate_positions),
                )
                .subquery()
            )
        else:
            movement_source = func.coalesce(
                WorkOrder.source_flow_node_id,
                ProductionMovement.source_flow_node_id,
            )
            ranked_movements = (
                select(
                    ProductionMovement.id.label("movement_id"),
                    ProductionMovement.production_item_id,
                    ProductionMovement.target_flow_node_id,
                    movement_source.label("source_flow_node_id"),
                    ProductionMovement.created_at.label("movement_created_at"),
                    func.row_number().over(
                        partition_by=(
                            ProductionMovement.production_item_id,
                            ProductionMovement.target_flow_node_id,
                            movement_source,
                        ),
                        order_by=(
                            ProductionMovement.created_at.desc(),
                            ProductionMovement.id.desc(),
                        ),
                    ).label("position_rank"),
                )
                .outerjoin(WorkOrder, WorkOrder.id == ProductionMovement.work_order_id)
                .where(
                    ProductionMovement.target_department_id == department.id,
                    tuple_(
                        ProductionMovement.production_item_id,
                        ProductionMovement.target_flow_node_id,
                        movement_source,
                    ).in_(candidate_positions),
                )
                .subquery()
            )
    latest_movements = {}
    if ranked_movements is not None:
        movement_ids = select(ranked_movements.c.movement_id).where(
            ranked_movements.c.position_rank == 1
        )
        if apply_member_filters and arrived_from:
            movement_ids = movement_ids.where(
                ranked_movements.c.movement_created_at
                >= datetime.combine(arrived_from, time.min, BUSINESS_TIMEZONE)
            )
        if apply_member_filters and arrived_to:
            movement_ids = movement_ids.where(
                ranked_movements.c.movement_created_at
                < datetime.combine(
                    arrived_to + timedelta(days=1), time.min, BUSINESS_TIMEZONE
                )
            )
        movements = list(
            session.scalars(
                select(ProductionMovement).where(
                    ProductionMovement.id.in_(movement_ids)
                )
            ).all()
        )
        if department.department_code == "assembly":
            latest_movements = {
                (item.production_item_id, item.target_flow_node_id): item
                for item in movements
            }
        else:
            movement_ids_by_position = {
                (
                    row.production_item_id,
                    row.target_flow_node_id,
                    row.source_flow_node_id,
                ): row.movement_id
                for row in session.execute(
                    select(ranked_movements).where(ranked_movements.c.position_rank == 1)
                )
            }
            movements_by_id = {item.id: item for item in movements}
            latest_movements = {
                position: movements_by_id[movement_id]
                for position, movement_id in movement_ids_by_position.items()
                if movement_id in movements_by_id
            }

    open_assembly_by_position: dict[tuple[int, str], WorkOrder] = {}
    assembly_stage_by_order: dict[int, str] = {}
    if department.department_code == "assembly" and candidate_positions:
        assembly_rows = session.execute(
            select(WorkOrderMaterial.production_item_id, WorkOrder)
            .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
            .where(
                tuple_(
                    WorkOrderMaterial.production_item_id,
                    WorkOrder.flow_node_id,
                ).in_(candidate_positions),
                WorkOrder.work_order_type == "assembly",
                WorkOrder.status == "open",
            )
            .order_by(WorkOrder.id.desc())
        ).all()
        for production_item_id, open_order in assembly_rows:
            open_assembly_by_position.setdefault(
                (production_item_id, open_order.flow_node_id),
                open_order,
            )
        batches_by_order: dict[int, list[WorkOrderBatch]] = {
            order.id: [] for order in open_assembly_by_position.values()
        }
        orders_by_id = {
            order.id: order for order in open_assembly_by_position.values()
        }
        if batches_by_order:
            for batch in session.scalars(
                select(WorkOrderBatch).where(
                    WorkOrderBatch.work_order_id.in_(list(batches_by_order))
                )
            ):
                batches_by_order[batch.work_order_id].append(batch)
        assembly_stage_by_order = {
            order_id: work_order_stage(
                orders_by_id[order_id],
                batches,
            )
            for order_id, batches in batches_by_order.items()
        }

    cards = []
    display_context = ProductionItemDisplayContext()
    for position in candidate_positions:
        if position in current_positions:
            continue
        production_item_id, node_id = position[:2]
        movement = latest_movements.get(position)
        if movement is None:
            continue
        open_assembly_order = open_assembly_by_position.get(
            (production_item_id, node_id)
        )
        cards.append(_historical_card(
            session,
            production_item_id,
            node_id,
            department,
            movement,
            open_assembly_order=open_assembly_order,
            assembly_status=(
                assembly_stage_by_order.get(open_assembly_order.id, "processing")
                if open_assembly_order is not None else "completed"
            ),
            display_context=display_context,
        ))
    return cards

def _historical_card(
    session,
    production_item_id,
    node_id,
    department,
    movement,
    *,
    display_context,
    open_assembly_order=None,
    assembly_status="completed",
):
    production_item = session.get(ProductionItem, production_item_id)
    display_context.production_items[production_item.id] = production_item
    context = load_production_flow(
        session,
        production_item,
        flow_cache=display_context.flow_cache,
        order_items=display_context.order_items,
        bom_items=display_context.bom_items,
    )
    display_context.order_items[context.order_item.id] = context.order_item
    if context.bom_item is not None:
        display_context.bom_items[context.bom_item.id] = context.bom_item
    order_item = context.order_item
    order = session.get(CustomerOrder, order_item.customer_order_id)
    product = session.get(Product, order_item.product_id)
    node = context.nodes.get(node_id, {})
    source_flow_node_id = movement.source_flow_node_id or ""
    movement_order = (
        session.get(WorkOrder, movement.work_order_id)
        if movement.work_order_id is not None else None
    )
    if (
        department.department_code != "assembly"
        and movement_order is not None
        and movement_order.source_flow_node_id is not None
    ):
        source_flow_node_id = movement_order.source_flow_node_id
    source = context.nodes.get(source_flow_node_id, {})
    workshop = (
        session.get(Workshop, node.get("workshop_id"))
        if node.get("workshop_id") else None
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
        "card_key": f"history:{production_item_id}:{node_id}:{movement.id}",
        "repository_id": None,
        "production_item_id": production_item_id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": context.bom_item.id if context.bom_item else None,
        "part_name": part_name,
        "part_no": part_no,
        "flow_node_id": node_id,
        "node_type": str(node.get("type") or ""),
        "source_flow_node_id": source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "material_source_name": _material_source_name(context, production_item),
        "workshop_id": workshop.id if workshop else 0,
        "available_procedures": [],
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": 0,
        "available_quantity": 0,
        "assembly_unit_quantity": context.bom_item.pcs if context.bom_item else 1,
        "assembly_required_source_ids": [],
        "assembly_material_key": production_item_material_key(production_item),
        "assembly_required_material_keys": [],
        "assembly_group_complete": not is_assembly_node,
        "assembly_output_name": node.get("output_name") if is_assembly_node else None,
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(movement.created_at),
        "work_status": assembly_status,
        "can_create_work_order": False,
    }
    if is_assembly_node:
        card["assembly_required_source_ids"] = _normal_input_source_ids(
            context.flow, node_id
        )
        card["assembly_required_material_keys"] = _normal_input_material_keys(
            context.flow, context.nodes, node_id
        )
    return card
