from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select, tuple_

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, business_iso
from models.engineering import Product, ProductBom
from models.organization import Department, Procedure, Workshop
from models.production import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError
from services.production_card_filters import (
    filter_and_paginate_assembly_groups,
    filter_and_paginate_cards,
)
from services.production_card_status import (
    position_statuses,
    reserved_quantities,
)
from services.production_flow import load_production_flow
from services.work_order_presenters import production_item_name


def list_production_cards(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None = None,
    arrived_from: date | None = None,
    arrived_to: date | None = None,
    work_status: str = "all",
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        cards = []
        if work_status != "completed" or department_code == "qc":
            cards.extend(
                _current_cards(
                    session, department, keyword, arrived_from, arrived_to
                )
            )
        if work_status in {"all", "completed"}:
            current_position_pairs = set(
                session.execute(
                    select(Repository.production_item_id, Repository.flow_node_id)
                    .where(Repository.department_id == department.id)
                    .distinct()
                ).all()
            )
            cards.extend(
                _historical_cards(
                    session,
                    department,
                    current_position_pairs,
                    keyword,
                    arrived_from,
                    arrived_to,
                )
            )
        if department_code == "assembly":
            return filter_and_paginate_assembly_groups(
                cards, page, page_size, keyword, arrived_from, arrived_to, work_status
            )
        return filter_and_paginate_cards(
            cards, page, page_size, keyword, arrived_from, arrived_to, work_status
        )


def _current_cards(
    session,
    department: Department,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
) -> list[dict]:
    latest_arrivals = (
        select(
            ProductionMovement.production_item_id.label("production_item_id"),
            ProductionMovement.target_flow_node_id.label("flow_node_id"),
            ProductionMovement.source_flow_node_id.label("source_flow_node_id"),
            func.max(ProductionMovement.created_at).label("arrived_at"),
        )
        .select_from(ProductionMovement)
        .join(
            Repository,
            and_(
                Repository.production_item_id == ProductionMovement.production_item_id,
                Repository.flow_node_id == ProductionMovement.target_flow_node_id,
                Repository.source_flow_node_id == ProductionMovement.source_flow_node_id,
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
            ProductionMovement.source_flow_node_id,
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
        .where(Repository.department_id == department.id)
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
    procedure = session.get(Procedure, node.get("procedure_id")) if node.get("procedure_id") else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(session, production_item, set())
        part_no = part_name
    card = {
        "card_key": f"repository:{repository.id}",
        "repository_id": repository.id,
        "production_item_id": production_item.id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": bom_item.id if bom_item else None,
        "part_name": part_name,
        "part_no": part_no,
        "flow_node_id": repository.flow_node_id,
        "source_flow_node_id": repository.source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
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
        "assembly_group_complete": department.department_code != "assembly",
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(arrived_at),
        "work_status": work_status,
        "can_create_work_order": department.department_code != "qc",
    }
    if department.department_code == "assembly":
        card["assembly_required_source_ids"] = _normal_input_source_ids(
            context.flow, repository.flow_node_id
        )
    return card


def _historical_cards(
    session,
    department,
    current_position_pairs,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
) -> list[dict]:
    if department.department_code == "qc":
        candidates = session.execute(
            select(WorkOrder.production_item_id, WorkOrderBatch.flow_node_id)
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(WorkOrderBatch.recorded_at.is_not(None))
            .distinct()
        ).all()
    elif department.department_code == "assembly":
        candidates = session.execute(
            select(
                WorkOrderMaterial.production_item_id,
                WorkOrder.flow_node_id,
            )
            .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
            .where(WorkOrder.procedure_id.is_(None), WorkOrder.status == "closed")
            .distinct()
        ).all()
    else:
        candidates = session.execute(
            select(WorkOrder.production_item_id, WorkOrder.flow_node_id)
            .join(Procedure, Procedure.id == WorkOrder.procedure_id)
            .join(Workshop, Workshop.id == Procedure.workshop_id)
            .where(
                Workshop.department_id == department.id,
                WorkOrder.status == "closed",
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
    ) if candidate_positions else None
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
        latest_movements = {
            (item.production_item_id, item.target_flow_node_id): item
            for item in session.scalars(
                select(ProductionMovement).where(ProductionMovement.id.in_(movement_ids))
            )
        }

    cards = []
    for production_item_id, node_id in candidate_positions:
        if (production_item_id, node_id) in current_position_pairs:
            continue
        movement = latest_movements.get((production_item_id, node_id))
        if movement is None:
            continue
        cards.append(_historical_card(session, production_item_id, node_id, department, movement))
    return cards


def _historical_card(session, production_item_id, node_id, department, movement):
    production_item = session.get(ProductionItem, production_item_id)
    context = load_production_flow(session, production_item)
    order_item = context.order_item
    order = session.get(CustomerOrder, order_item.customer_order_id)
    product = session.get(Product, order_item.product_id)
    node = context.nodes.get(node_id, {})
    source = context.nodes.get(movement.source_flow_node_id, {})
    procedure = session.get(Procedure, node.get("procedure_id")) if node.get("procedure_id") else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(session, production_item, set())
        part_no = part_name
    card = {
        "card_key": f"history:{production_item_id}:{node_id}:{movement.id}",
        "repository_id": None,
        "production_item_id": production_item_id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": context.bom_item.id if context.bom_item else None,
        "part_name": part_name,
        "part_no": part_no,
        "flow_node_id": node_id,
        "source_flow_node_id": movement.source_flow_node_id or "",
        "source_node_label": source.get("label", "未知来源"),
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": 0,
        "available_quantity": 0,
        "assembly_unit_quantity": context.bom_item.pcs if context.bom_item else 1,
        "assembly_required_source_ids": [],
        "assembly_group_complete": department.department_code != "assembly",
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(movement.created_at),
        "work_status": "completed",
        "can_create_work_order": False,
    }
    if department.department_code == "assembly":
        card["assembly_required_source_ids"] = _normal_input_source_ids(
            context.flow, node_id
        )
    return card


def _normal_input_source_ids(flow: dict, node_id: str) -> list[str]:
    return list(dict.fromkeys(
        edge["source_node_id"]
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
        and edge.get("route_type", "normal") == "normal"
        and edge.get("source_node_id")
    ))
