from sqlalchemy import select

from database import SessionLocal
from modules.organization.model_api import Department, Procedure, Workshop
from modules.quality.model_api import WorkOrderBatch
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.production_core.persistence import ProductionItem, Repository, WorkOrder
from modules.errors import DomainError
from modules.production_core.card_filters import (
    filter_and_paginate_assembly_groups,
    filter_and_paginate_cards,
)
from modules.production_core.card_status import work_order_stage
from modules.production_core.cards import (
    _current_cards,
    _historical_cards,
)
from modules.production_core.flow import load_production_flow
from modules.production_core.work_order_progress import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
)


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
            cards.extend(active_cards)
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
                _fulfilled_assembly_positions(session, cards),
            )
        if department_code != "purchasing":
            _simplify_production_card_statuses(cards)
        return filter_and_paginate_cards(
            cards,
            page,
            page_size,
            keyword,
            workshop_name,
            work_status,
        )


def _simplify_production_card_statuses(cards: list[dict]) -> None:
    for card in cards:
        if card["work_status"] not in {"unprocessed", "completed"}:
            card["work_status"] = "processing"


def _fulfilled_assembly_positions(
    session,
    cards: list[dict],
) -> set[tuple[int, str]]:
    positions = {
        (item["customer_order_item_id"], item["flow_node_id"])
        for item in cards
        if item.get("node_type") == "assembly"
        and not item["card_key"].startswith("history:")
    }
    if not positions:
        return set()
    order_item_ids = {position[0] for position in positions}
    plan_rows = session.execute(
        select(
            ProductionPlanItem.customer_order_item_id,
            ProductionPlanItem.flow_node_id,
            ProductionPlanItem.planned_production_quantity,
        )
        .join(ProductionPlan, ProductionPlan.id == ProductionPlanItem.production_plan_id)
        .where(
            ProductionPlan.status == "confirmed",
            ProductionPlanItem.item_type == "assembly",
            ProductionPlanItem.customer_order_item_id.in_(order_item_ids),
        )
    ).all()
    planned = {
        (row.customer_order_item_id, row.flow_node_id): row.planned_production_quantity
        for row in plan_rows
        if (row.customer_order_item_id, row.flow_node_id) in positions
    }
    if not planned:
        return set()
    order_rows = session.execute(
        select(WorkOrder, ProductionItem)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            WorkOrder.work_order_type == "assembly",
            WorkOrder.status.in_(("open", "closed")),
            ProductionItem.customer_order_item_id.in_(order_item_ids),
            WorkOrder.flow_node_id.in_({position[1] for position in positions}),
        )
    ).all()
    orders = [row.WorkOrder for row in order_rows]
    batches_by_order: dict[int, list[WorkOrderBatch]] = {}
    if orders:
        for batch in session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_([order.id for order in orders])
            )
        ).all():
            batches_by_order.setdefault(batch.work_order_id, []).append(batch)
    completed: dict[tuple[int, str], int] = {}
    output_units: dict[int, int] = {}
    for row in order_rows:
        order = row.WorkOrder
        production_item = row.ProductionItem
        key = (production_item.customer_order_item_id, order.flow_node_id)
        if key not in planned:
            continue
        if production_item.id not in output_units:
            node = load_production_flow(session, production_item).nodes.get(
                order.flow_node_id,
                {},
            )
            output_units[production_item.id] = max(
                int(node.get("output_pcs") or 1),
                1,
            )
        progress = calculate_assembly_output_progress(
            order,
            batches_by_order.get(order.id, []),
            output_units[production_item.id],
        )
        completed[key] = completed.get(key, 0) + progress.qualified_quantity
    return {
        key for key, planned_quantity in planned.items()
        if completed.get(key, 0) >= planned_quantity
    }


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
