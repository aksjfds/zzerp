from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import exists, func, or_, select

from database import SessionLocal
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
        cards = _current_cards(session, department)
        current_positions = {
            (item["production_item_id"], item["flow_node_id"]) for item in cards
        }
        cards.extend(_historical_cards(session, department, current_positions))
        if department_code == "assembly":
            return _filter_and_paginate_assembly_groups(
                cards, page, page_size, keyword, arrived_from, arrived_to, work_status
            )
        cards = [
            item for item in cards
            if _matches_filters(item, keyword, arrived_from, arrived_to, work_status)
        ]
        cards.sort(key=lambda item: (item["arrived_at"] or "", item["card_key"]), reverse=True)
        total = len(cards)
        start = (page - 1) * page_size
        return cards[start:start + page_size], total


def _current_cards(session, department: Department) -> list[dict]:
    rows = session.execute(
        select(Repository, ProductionItem, CustomerOrderItem, CustomerOrder, Product, ProductBom)
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
        .join(Product, Product.id == CustomerOrderItem.product_id)
        .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
        .where(Repository.department_id == department.id)
    ).all()
    repository_ids = [row.Repository.id for row in rows]
    reserved_by_id = _reserved_quantities(session, repository_ids)
    return [
        _current_card(
            session, row.Repository, row.ProductionItem, row.CustomerOrderItem,
            row.CustomerOrder, row.Product, row.ProductBom, department,
            reserved_by_id.get(row.Repository.id, 0),
        )
        for row in rows
    ]


def _reserved_quantities(session, repository_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    if not repository_ids:
        return result
    for repository_id, quantity in session.execute(
        select(WorkOrder.repository_id, func.sum(WorkOrder.quantity - WorkOrder.completed_quantity))
        .where(WorkOrder.repository_id.in_(repository_ids), WorkOrder.status == "open")
        .group_by(WorkOrder.repository_id)
    ):
        result[repository_id] = quantity
    for repository_id, quantity in session.execute(
        select(WorkOrderMaterial.repository_id, func.sum(WorkOrderMaterial.quantity))
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
        .where(WorkOrderMaterial.repository_id.in_(repository_ids), WorkOrder.status == "open")
        .group_by(WorkOrderMaterial.repository_id)
    ):
        result[repository_id] = result.get(repository_id, 0) + quantity
    return result


def _current_card(
    session, repository, production_item, order_item, order, product, bom_item,
    department, reserved,
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
    return {
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
        "delivery_date": order_item.delivery_date,
        "arrived_at": _arrival_time(
            session, production_item.id, repository.flow_node_id, department.id
        ),
        "work_status": _position_status(
            session, department.department_code, production_item.id, repository.flow_node_id
        ),
        "can_create_work_order": department.department_code != "qc",
    }


def _historical_cards(session, department, current_positions) -> list[dict]:
    if department.department_code == "qc":
        rows = session.execute(
            select(WorkOrderBatch, WorkOrder)
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(WorkOrderBatch.recorded_at.is_not(None))
        ).all()
        candidates = [(row.WorkOrder.production_item_id, row.WorkOrderBatch.flow_node_id) for row in rows]
    else:
        condition = WorkOrder.procedure_id.is_(None) if department.department_code == "assembly" else Workshop.department_id == department.id
        orders = session.execute(
            select(WorkOrder)
            .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
            .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
            .where(condition, WorkOrder.status == "closed")
        ).scalars().all()
        if department.department_code == "assembly":
            candidates = [
                (production_item_id, order.flow_node_id)
                for order in orders
                for production_item_id in session.scalars(
                    select(WorkOrderMaterial.production_item_id).where(
                        WorkOrderMaterial.work_order_id == order.id
                    )
                )
            ]
        else:
            candidates = [(order.production_item_id, order.flow_node_id) for order in orders]
    cards = []
    for production_item_id, node_id in dict.fromkeys(candidates):
        if (production_item_id, node_id) in current_positions:
            continue
        movement = session.scalar(
            select(ProductionMovement)
            .where(
                ProductionMovement.production_item_id == production_item_id,
                ProductionMovement.target_department_id == department.id,
                ProductionMovement.target_flow_node_id == node_id,
            )
            .order_by(ProductionMovement.created_at.desc(), ProductionMovement.id.desc())
            .limit(1)
        )
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
    return {
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
        "delivery_date": order_item.delivery_date,
        "arrived_at": movement.created_at.isoformat(timespec="minutes"),
        "work_status": "completed",
        "can_create_work_order": False,
    }


def _position_status(session, department_code, production_item_id, node_id):
    if department_code == "qc":
        pending = session.scalar(
            select(func.count(WorkOrderBatch.id))
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(
                WorkOrder.production_item_id == production_item_id,
                WorkOrderBatch.flow_node_id == node_id,
                WorkOrderBatch.recorded_at.is_(None),
            )
        )
        return "unprocessed" if pending else "completed"
    statement = select(WorkOrder).where(WorkOrder.flow_node_id == node_id)
    if department_code == "assembly":
        statement = statement.where(or_(
            WorkOrder.production_item_id == production_item_id,
            exists(select(WorkOrderMaterial.id).where(
                WorkOrderMaterial.work_order_id == WorkOrder.id,
                WorkOrderMaterial.production_item_id == production_item_id,
            )),
        ))
    else:
        statement = statement.where(WorkOrder.production_item_id == production_item_id)
    orders = [item for item in session.scalars(statement).all() if item.status != "cancelled"]
    if any(item.status == "open" for item in orders):
        return "processing"
    latest_closed = max(
        (item.closed_at for item in orders if item.status == "closed" and item.closed_at),
        default=None,
    )
    latest_arrival = session.scalar(
        select(func.max(ProductionMovement.created_at)).where(
            ProductionMovement.production_item_id == production_item_id,
            ProductionMovement.target_flow_node_id == node_id,
        )
    )
    return "completed" if latest_closed and (
        latest_arrival is None or latest_closed >= latest_arrival
    ) else "unprocessed"


def _arrival_time(session, production_item_id, node_id, department_id):
    value = session.scalar(
        select(func.max(ProductionMovement.created_at)).where(
            ProductionMovement.production_item_id == production_item_id,
            ProductionMovement.target_flow_node_id == node_id,
            ProductionMovement.target_department_id == department_id,
        )
    )
    return value.isoformat(timespec="minutes") if value else None


def _matches_filters(item, keyword, arrived_from, arrived_to, work_status):
    if work_status != "all" and item["work_status"] != work_status:
        return False
    arrived_at = datetime.fromisoformat(item["arrived_at"]) if item["arrived_at"] else None
    if arrived_from and (arrived_at is None or arrived_at < datetime.combine(arrived_from, time.min)):
        return False
    if arrived_to and (arrived_at is None or arrived_at >= datetime.combine(arrived_to + timedelta(days=1), time.min)):
        return False
    value = (keyword or "").strip().lower()
    if not value:
        return True
    haystack = " ".join((item["product_name"], item["factory_code"], item["part_name"], item["part_no"])).lower()
    tokens = [part for part in value.removesuffix("装配体").replace("-", " ").split() if part]
    return value in haystack or bool(tokens) and all(token in haystack for token in tokens)


def _filter_and_paginate_assembly_groups(
    cards, page, page_size, keyword, arrived_from, arrived_to, work_status
):
    groups = defaultdict(list)
    for item in cards:
        key = (item["customer_order_item_id"], item["flow_node_id"])
        groups[key].append(item)
    filtered = []
    for group in groups.values():
        status = "processing" if any(item["work_status"] == "processing" for item in group) else (
            "completed" if all(item["work_status"] == "completed" for item in group) else "unprocessed"
        )
        arrived_at = max((item["arrived_at"] or "" for item in group), default="") or None
        representative = {
            **group[0],
            "work_status": status,
            "arrived_at": arrived_at,
            "part_name": "-".join(dict.fromkeys(item["part_name"] for item in group)),
            "part_no": " ".join(item["part_no"] for item in group),
        }
        if not _matches_filters(
            representative, keyword, arrived_from, arrived_to, work_status
        ):
            continue
        for item in group:
            item["work_status"] = status
            item["arrived_at"] = arrived_at
        filtered.append(group)
    ordered = sorted(filtered, key=lambda group: group[0]["arrived_at"] or "", reverse=True)
    total = len(ordered)
    selected = ordered[(page - 1) * page_size:page * page_size]
    return [item for group in selected for item in group], total
