from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, or_, select, tuple_

from domain.time import BUSINESS_TIMEZONE, business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Procedure, Workshop
from modules.planning.model_api import ProductionPlan
from modules.standard_execution.model_api import ProcedureTagSet
from modules.assembly.model_api import WorkOrderMaterial
from modules.quality.model_api import WorkOrderBatch
from modules.standard_execution.model_api import ProcedureTagStock
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
    reserved_tag_quantities,
    tag_stock_statuses,
)
from modules.production_core.flow import load_production_flow
from modules.standard_execution.tag_api import (
    configured_tag_suggestions,
    is_final_tag_set,
    serialize_tag,
    serialize_tag_set,
    tag_suggestions,
)
from modules.production_core.work_order_presenters import production_item_name


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


def _tag_stock_cards(
    session,
    department: Department,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
) -> list[dict]:
    arrival_tag_set_id = case(
        (
            ProductionMovement.movement_type == "qc_rework",
            WorkOrder.source_tag_set_id,
        ),
        else_=WorkOrder.target_tag_set_id,
    )
    latest_arrivals = (
        select(
            ProductionMovement.production_item_id.label("production_item_id"),
            ProductionMovement.target_flow_node_id.label("flow_node_id"),
            WorkOrder.source_flow_node_id.label("source_flow_node_id"),
            arrival_tag_set_id.label("tag_set_id"),
            func.max(ProductionMovement.created_at).label("arrived_at"),
        )
        .join(WorkOrder, WorkOrder.id == ProductionMovement.work_order_id)
        .outerjoin(
            WorkOrderBatch,
            WorkOrderBatch.id == ProductionMovement.work_order_batch_id,
        )
        .where(
            ProductionMovement.target_department_id == department.id,
            ProductionMovement.target_flow_node_id.is_not(None),
            ProductionMovement.movement_type.in_(
                ("process", "purchase_receipt", "qc_qualified", "qc_rework")
            ),
        )
        .group_by(
            ProductionMovement.production_item_id,
            ProductionMovement.target_flow_node_id,
            WorkOrder.source_flow_node_id,
            arrival_tag_set_id,
        )
        .subquery()
    )
    statement = (
        select(
            ProcedureTagStock,
            ProductionItem,
            CustomerOrderItem,
            CustomerOrder,
            Product,
            ProductBom,
            latest_arrivals.c.arrived_at,
        )
        .join(
            ProductionItem,
            ProductionItem.id == ProcedureTagStock.production_item_id,
        )
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionItem.customer_order_item_id,
        )
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
        .join(ProductionPlan, ProductionPlan.customer_order_id == CustomerOrder.id)
        .join(Product, Product.id == CustomerOrderItem.product_id)
        .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
        .outerjoin(
            latest_arrivals,
            and_(
                latest_arrivals.c.production_item_id
                == ProcedureTagStock.production_item_id,
                latest_arrivals.c.flow_node_id == ProcedureTagStock.flow_node_id,
                latest_arrivals.c.source_flow_node_id
                == ProcedureTagStock.source_flow_node_id,
                latest_arrivals.c.tag_set_id == ProcedureTagStock.tag_set_id,
            ),
        )
        .where(
            ProcedureTagStock.department_id == department.id,
            ProductionPlan.status == "confirmed",
        )
    )
    statement = _apply_current_source_filters(
        statement,
        latest_arrivals.c.arrived_at,
        keyword,
        arrived_from,
        arrived_to,
    )
    rows = session.execute(statement).all()
    stock_ids = [row.ProcedureTagStock.id for row in rows]
    reserved_by_id = reserved_tag_quantities(session, stock_ids)
    status_by_id = tag_stock_statuses(session, stock_ids)
    return [
        _tag_stock_card(
            session,
            row.ProcedureTagStock,
            row.ProductionItem,
            row.CustomerOrderItem,
            row.CustomerOrder,
            row.Product,
            row.ProductBom,
            department,
            reserved_by_id.get(row.ProcedureTagStock.id, 0),
            row.arrived_at,
            status_by_id[row.ProcedureTagStock.id],
        )
        for row in rows
    ]


def _tag_stock_card(
    session,
    stock,
    production_item,
    order_item,
    order,
    product,
    bom_item,
    department,
    reserved,
    arrived_at,
    work_status,
) -> dict:
    context = load_production_flow(session, production_item)
    node = context.nodes.get(stock.flow_node_id, {})
    source = context.nodes.get(stock.source_flow_node_id, {})
    tag_set = session.get(ProcedureTagSet, stock.tag_set_id)
    procedure = session.get(Procedure, tag_set.procedure_id) if tag_set else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    final_tag_set = bool(procedure) and is_final_tag_set(
        session,
        production_item,
        procedure.id,
        stock.tag_set_id,
    )
    suggestions = tag_suggestions(session, procedure.id) if procedure else []
    configured_suggestions = configured_tag_suggestions(
        session,
        production_item,
        procedure.id,
    ) if procedure else []
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(session, production_item, set())
        part_no = part_name
    return {
        "card_key": f"tag-stock:{stock.id}",
        "repository_id": None,
        "tag_stock_id": stock.id,
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
        "flow_node_id": stock.flow_node_id,
        "source_flow_node_id": stock.source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "procedure_id": procedure.id if procedure else None,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "current_tag_set_name": serialize_tag_set(session, stock.tag_set_id)["tag_set_name"],
        "available_tags": [serialize_tag(item) for item in suggestions],
        "configured_tags": [
            serialize_tag(item) for item in configured_suggestions
        ],
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": stock.quantity,
        "available_quantity": max(stock.quantity - reserved, 0),
        "assembly_unit_quantity": bom_item.pcs if bom_item else int(
            context.nodes.get(production_item.origin_flow_node_id, {}).get("output_pcs", 1)
        ),
        "assembly_required_source_ids": [],
        "assembly_group_complete": True,
        "assembly_output_name": None,
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(arrived_at),
        "work_status": work_status,
        "can_create_work_order": (
            bool(procedure)
            and procedure.procedure_type == "standard"
            and bool(configured_suggestions)
            and not final_tag_set
            and reserved < stock.quantity
        ),
    }


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
    suggestions = tag_suggestions(session, procedure.id) if procedure else []
    configured_suggestions = configured_tag_suggestions(
        session,
        production_item,
        procedure.id,
    ) if procedure else []
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(session, production_item, set())
        part_no = part_name
    card = {
        "card_key": f"repository:{repository.id}",
        "repository_id": repository.id,
        "tag_stock_id": None,
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
        "source_flow_node_id": repository.source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "procedure_id": procedure.id if procedure else None,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "current_tag_set_name": (
            "未打标记"
            if procedure and procedure.procedure_type == "standard"
            else node.get("label", "")
        ),
        "available_tags": [serialize_tag(item) for item in suggestions],
        "configured_tags": [
            serialize_tag(item) for item in configured_suggestions
        ],
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
        "assembly_output_name": (
            node.get("output_name")
            if department.department_code == "assembly" else None
        ),
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(arrived_at),
        "work_status": work_status,
        "can_create_work_order": (
            department.department_code == "assembly"
            or (
                procedure is not None
                and (
                    procedure.procedure_type != "standard"
                    or bool(configured_suggestions)
                )
                and reserved < repository.quantity
            )
        ),
    }
    if department.department_code == "assembly":
        card["assembly_required_source_ids"] = _normal_input_source_ids(
            context.flow, repository.flow_node_id
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

    cards = []
    for position in candidate_positions:
        if position in current_positions:
            continue
        production_item_id, node_id = position[:2]
        movement = latest_movements.get(position)
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
    source_flow_node_id = movement.source_flow_node_id or ""
    movement_order = (
        session.get(WorkOrder, movement.work_order_id)
        if movement.work_order_id is not None
        else None
    )
    if (
        department.department_code != "assembly"
        and movement_order is not None
        and movement_order.source_flow_node_id is not None
    ):
        source_flow_node_id = movement_order.source_flow_node_id
    source = context.nodes.get(source_flow_node_id, {})
    open_assembly_order = None
    if department.department_code == "assembly":
        open_assembly_order = session.scalar(
            select(WorkOrder)
            .join(WorkOrderMaterial, WorkOrderMaterial.work_order_id == WorkOrder.id)
            .where(
                WorkOrderMaterial.production_item_id == production_item_id,
                WorkOrder.flow_node_id == node_id,
                WorkOrder.work_order_type == "assembly",
                WorkOrder.status == "open",
            )
            .order_by(WorkOrder.id.desc())
            .limit(1)
        )
    procedure = session.get(Procedure, node.get("procedure_id")) if node.get("procedure_id") else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    part_no, part_name = context.item_name(production_item)
    if context.bom_item is None:
        part_name = production_item_name(session, production_item, set())
        part_no = part_name
    card = {
        "card_key": f"history:{production_item_id}:{node_id}:{movement.id}",
        "repository_id": None,
        "tag_stock_id": None,
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
        "source_flow_node_id": source_flow_node_id,
        "source_node_label": source.get("label", "未知来源"),
        "procedure_id": procedure.id if procedure else None,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "current_tag_set_name": "加工中" if open_assembly_order else "已完成",
        "available_tags": [],
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": 0,
        "available_quantity": 0,
        "assembly_unit_quantity": context.bom_item.pcs if context.bom_item else 1,
        "assembly_required_source_ids": [],
        "assembly_group_complete": department.department_code != "assembly",
        "assembly_output_name": (
            node.get("output_name")
            if department.department_code == "assembly" else None
        ),
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(movement.created_at),
        "work_status": "processing" if open_assembly_order else "completed",
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
        and edge.get("source_node_id")
    ))
