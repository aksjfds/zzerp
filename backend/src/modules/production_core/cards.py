from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, or_, select, tuple_

from domain.time import BUSINESS_TIMEZONE, business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Procedure, Workshop
from modules.planning.model_api import ProductionPlan
from modules.assembly.model_api import WorkOrderMaterial
from modules.quality.model_api import WorkOrderBatch
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.card_status import (
    position_statuses,
    reserved_quantities,
    work_order_stage,
)
from modules.production_core.flow import assembly_material_key, load_production_flow
from modules.organization.read_api import get_procedure_views
from modules.production_core.work_order_presenters import production_item_name


def _workshop_procedures(
    session, workshop_id: int | None, procedure_type: str, input_mode: str,
):
    if workshop_id is None:
        return []
    cache = session.info.get("workshop_procedure_views")
    if cache is None:
        cache = {}
        for item in get_procedure_views(session):
            cache.setdefault(
                (item.workshop_id, item.procedure_type, item.input_mode), []
            ).append(item)
        session.info["workshop_procedure_views"] = cache
    return cache.get((workshop_id, procedure_type, input_mode), [])


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

    keyword_filter = _source_keyword_filter(keyword)
    if keyword_filter is not None:
        statement = statement.where(keyword_filter)
    return statement


def _source_keyword_filter(keyword: str | None):
    value = (keyword or "").strip().lower()
    if not value:
        return None
    tokens = [
        item
        for item in value.removesuffix("装配体").replace("-", " ").split()
        if item
    ]
    searchable_columns = (
        Product.product_name,
        Product.factory_code,
        ProductBom.part_name,
        ProductBom.part_no,
    )
    token_filter = and_(
        *[
            or_(*(column.ilike(f"%{token}%") for column in searchable_columns))
            for token in tokens
        ]
    ) if tokens else None
    return (
        or_(ProductionItem.product_bom_id.is_(None), token_filter)
        if token_filter is not None
        else None
    )


def _current_card(
    session, repository, production_item, order_item, order, product, bom_item,
    department, reserved, arrived_at, work_status,
) -> dict:
    context = load_production_flow(session, production_item)
    node = context.nodes.get(repository.flow_node_id, {})
    source = context.nodes.get(repository.source_flow_node_id, {})
    workshop = (
        session.get(Workshop, node.get("workshop_id"))
        if node.get("workshop_id") else None
    )
    procedures = _workshop_procedures(
        session,
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
        part_name = production_item_name(session, production_item, set())
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
        "assembly_material_key": _production_item_material_key(production_item),
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
    keyword_filter = _source_keyword_filter(keyword) if apply_member_filters else None
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
        ))
    return cards


def _historical_card(
    session,
    production_item_id,
    node_id,
    department,
    movement,
    *,
    open_assembly_order=None,
    assembly_status="completed",
):
    production_item = session.get(ProductionItem, production_item_id)
    context = load_production_flow(session, production_item)
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
        part_name = production_item_name(session, production_item, set())
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
        "assembly_material_key": _production_item_material_key(production_item),
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

def _material_source_name(context, production_item) -> str:
    current_id = production_item.origin_flow_node_id
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        target = context.normal_target(current_id)
        if target is None:
            break
        if target.get("type") == "process":
            return str(target.get("label") or "路线")
        if target.get("type") in {"assembly", "shipping"}:
            break
        current_id = str(target.get("id") or "")
    return "装配体" if production_item.product_bom_id is None else "直接来源"


def _normal_input_source_ids(flow: dict, node_id: str) -> list[str]:
    return list(dict.fromkeys(
        edge["source_node_id"]
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
        and edge.get("source_node_id")
    ))


def _normal_input_material_keys(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> list[str]:
    return list(dict.fromkeys(
        key
        for source_id in _normal_input_source_ids(flow, node_id)
        if (key := assembly_material_key(flow, nodes, source_id)) is not None
    ))


def _production_item_material_key(production_item) -> str:
    if production_item.product_bom_id is not None:
        return f"part:{production_item.product_bom_id}"
    return f"assembly:{production_item.origin_flow_node_id}"
