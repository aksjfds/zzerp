from sqlalchemy import select

from database import SessionLocal
from domain.time import business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Procedure, Workshop
from modules.quality.model_api import WorkOrderBatch
from modules.standard_execution.model_api import ProcedureTagStock
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.card_filters import (
    filter_and_paginate_assembly_groups,
    filter_and_paginate_cards,
)
from modules.production_core.cards import (
    _current_cards,
    _historical_cards,
    _tag_stock_cards,
)
from modules.production_core.flow import load_production_flow
from modules.standard_execution.tag_api import (
    configured_tag_suggestions,
    serialize_tag,
    tag_suggestions,
)
from modules.production_core.work_order_presenters import production_item_name
from modules.production_core.work_order_progress import calculate_work_order_progress


def list_production_cards(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None = None,
    workshop_name: str | None = None,
    work_status: str = "all",
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        if department_code == "qc":
            return [], 0
        cards = []
        if work_status != "completed":
            active_cards = _current_cards(session, department, None, None, None)
            if department_code == "assembly":
                active_cards.extend(
                    _historical_cards(
                        session,
                        department,
                        _current_positions(session, department),
                        keyword,
                        None,
                        None,
                    )
                )
            else:
                active_cards.extend(
                    _tag_stock_cards(session, department, None, None, None)
                )
                active_cards.extend(_pending_standard_cards(session, department))
            cards.extend(_aggregate_standard_parent_cards(session, active_cards))
        if work_status in {"all", "completed"} and (
            department_code != "assembly" or work_status == "completed"
        ):
            cards.extend(
                _historical_cards(
                    session,
                    department,
                    _current_positions(session, department),
                    keyword,
                    None,
                    None,
                )
            )
        if department_code == "assembly":
            return filter_and_paginate_assembly_groups(
                cards,
                page,
                page_size,
                keyword,
                workshop_name,
                work_status,
            )
        return filter_and_paginate_cards(
            cards,
            page,
            page_size,
            keyword,
            workshop_name,
            work_status,
        )


def _current_positions(session, department: Department) -> set[tuple]:
    if department.department_code == "assembly":
        return set(
            session.execute(
                select(Repository.production_item_id, Repository.flow_node_id)
                .where(Repository.department_id == department.id)
                .distinct()
            ).all()
        )
    positions = set(
        session.execute(
            select(
                Repository.production_item_id,
                Repository.flow_node_id,
                Repository.source_flow_node_id,
            )
            .where(Repository.department_id == department.id)
            .distinct()
        ).all()
    )
    positions.update(
        session.execute(
            select(
                ProcedureTagStock.production_item_id,
                ProcedureTagStock.flow_node_id,
                ProcedureTagStock.source_flow_node_id,
            )
            .where(ProcedureTagStock.department_id == department.id)
            .distinct()
        ).all()
    )
    positions.update(
        session.execute(
            select(
                WorkOrder.production_item_id,
                WorkOrder.flow_node_id,
                WorkOrder.source_flow_node_id,
            )
            .join(WorkOrderBatch, WorkOrderBatch.work_order_id == WorkOrder.id)
            .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
            .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
            .where(
                Workshop.department_id == department.id,
                Procedure.procedure_type == "standard",
                WorkOrderBatch.recorded_at.is_(None),
            )
            .distinct()
        ).all()
    )
    return positions


def _aggregate_standard_parent_cards(session, cards: list[dict]) -> list[dict]:
    groups: dict[tuple[int, str, str], list[dict]] = {}
    passthrough: list[dict] = []
    for card in cards:
        procedure = (
            session.get(Procedure, card.get("procedure_id"))
            if card.get("procedure_id")
            else None
        )
        if procedure is None or procedure.procedure_type != "standard":
            passthrough.append(card)
            continue
        key = (
            card["production_item_id"],
            card["flow_node_id"],
            card["source_flow_node_id"],
        )
        groups.setdefault(key, []).append(card)

    for (production_item_id, flow_node_id, source_flow_node_id), group in groups.items():
        representative = next(
            (item for item in group if item.get("repository_id") is not None),
            group[0],
        )
        pending_qc_quantity = sum(
            item.get("_pending_qc_quantity", 0) for item in group
        )
        openable_quantity = sum(
            item["available_quantity"]
            for item in group
            if item.get("can_create_work_order", False)
        )
        status = (
            "processing"
            if pending_qc_quantity
            or any(item["work_status"] == "processing" for item in group)
            else "unprocessed"
        )
        arrived_at = max(
            (item["arrived_at"] or "" for item in group),
            default="",
        ) or None
        public_representative = {
            key: value
            for key, value in representative.items()
            if not key.startswith("_")
        }
        passthrough.append(
            {
                **public_representative,
                "card_key": (
                    f"production:{production_item_id}:{flow_node_id}:"
                    f"{source_flow_node_id}"
                ),
                "repository_id": None,
                "tag_stock_id": None,
                "current_tag_set_name": "标记组合",
                "quantity": sum(item["quantity"] for item in group)
                + pending_qc_quantity,
                "available_quantity": openable_quantity,
                "arrived_at": arrived_at,
                "work_status": status,
                "can_create_work_order": any(
                    item.get("can_create_work_order", False) for item in group
                ),
            }
        )
    return passthrough


def _pending_standard_cards(session, department: Department) -> list[dict]:
    rows = session.execute(
        select(
            WorkOrder,
            ProductionItem,
            CustomerOrderItem,
            CustomerOrder,
            Product,
            ProductBom,
            Procedure,
            Workshop,
        )
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionItem.customer_order_item_id,
        )
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
        .join(Product, Product.id == CustomerOrderItem.product_id)
        .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
        .join(Procedure, Procedure.id == WorkOrder.procedure_id)
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .where(
            WorkOrder.status == "open",
            WorkOrder.work_order_type == "tag",
            Procedure.procedure_type == "standard",
            Workshop.department_id == department.id,
        )
    ).all()
    cards = []
    for row in rows:
        batches = list(session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id == row.WorkOrder.id
            )
        ).all())
        progress = calculate_work_order_progress(row.WorkOrder, batches)
        if progress.pending_qc_quantity == 0 and progress.rework_pending_quantity == 0:
            continue
        production_item = row.ProductionItem
        context = load_production_flow(session, production_item)
        source = context.nodes.get(row.WorkOrder.source_flow_node_id, {})
        part_no, part_name = context.item_name(production_item)
        if context.bom_item is None:
            part_name = production_item_name(session, production_item, set())
            part_no = part_name
        movement_at = session.scalar(
            select(ProductionMovement.created_at)
            .where(
                ProductionMovement.work_order_id == row.WorkOrder.id,
                ProductionMovement.movement_type.in_(("process", "purchase_receipt")),
            )
            .order_by(ProductionMovement.id.desc())
            .limit(1)
        )
        cards.append(
            {
                "card_key": f"open-tag-order:{row.WorkOrder.id}",
                "repository_id": None,
                "tag_stock_id": None,
                "production_item_id": production_item.id,
                "customer_order_item_id": row.CustomerOrderItem.id,
                "customer_order_no": row.CustomerOrder.customer_order_no,
                "customer_name": row.CustomerOrder.customer.customer_name,
                "product_id": row.Product.id,
                "product_version": row.CustomerOrderItem.product_version,
                "product_name": row.Product.product_name,
                "factory_code": row.Product.factory_code,
                "product_bom_id": row.ProductBom.id if row.ProductBom else None,
                "part_name": part_name,
                "part_no": part_no,
                "flow_node_id": row.WorkOrder.flow_node_id,
                "source_flow_node_id": row.WorkOrder.source_flow_node_id,
                "source_node_label": source.get("label", "未知来源"),
                "procedure_id": row.Procedure.id,
                "procedure_name": row.Procedure.procedure_name,
                "current_tag_set_name": (
                    "待返工"
                    if progress.rework_pending_quantity
                    else "质检中"
                ),
                "available_tags": [
                    serialize_tag(item)
                    for item in tag_suggestions(session, row.Procedure.id)
                ],
                "configured_tags": [
                    serialize_tag(item)
                    for item in configured_tag_suggestions(
                        session,
                        production_item,
                        row.Procedure.id,
                    )
                ],
                "workshop_name": row.Workshop.workshop_name,
                "department_id": department.id,
                "department_name": department.department_name,
                "department_code": department.department_code,
                "quantity": 0,
                "available_quantity": 0,
                "assembly_unit_quantity": (
                    row.ProductBom.pcs
                    if row.ProductBom
                    else int(
                        context.nodes.get(
                            production_item.origin_flow_node_id,
                            {},
                        ).get("output_pcs", 1)
                    )
                ),
                "assembly_required_source_ids": [],
                "assembly_group_complete": True,
                "delivery_date": row.CustomerOrderItem.delivery_date,
                "arrived_at": business_iso(
                    movement_at
                    or row.WorkOrder.closed_at
                    or row.WorkOrder.created_at
                ),
                "work_status": "processing",
                "can_create_work_order": False,
                "_pending_qc_quantity": progress.pending_qc_quantity,
            }
        )
    return cards
