from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from models.organization import Department, Procedure, ProcedureTagSet, Workshop
from models.production import (
    ProcedureTagStock,
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from services.errors import DomainError
from services.procedure_tags import serialize_tag_set
from services.production_card_status import reserved_quantities, reserved_tag_quantities
from services.production_flow import load_production_flow


def list_tag_cards(
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
) -> list[dict]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        production_item = session.get(ProductionItem, production_item_id)
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        if production_item is None:
            raise DomainError("production_item_not_found", "生产配件不存在", status_code=404)
        context = load_production_flow(session, production_item)
        node = context.nodes.get(flow_node_id)
        procedure = (
            session.get(Procedure, node.get("procedure_id"))
            if node and node.get("type") == "process"
            else None
        )
        workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
        if (
            procedure is None
            or procedure.procedure_type != "standard"
            or workshop is None
            or workshop.department_id != department.id
        ):
            raise DomainError("tag_cards_not_available", "当前位置不支持生产标记")

        repository = session.scalar(
            select(Repository).where(
                Repository.production_item_id == production_item.id,
                Repository.flow_node_id == flow_node_id,
                Repository.source_flow_node_id == source_flow_node_id,
                Repository.department_id == department.id,
            )
        )
        stocks = list(
            session.scalars(
                select(ProcedureTagStock).where(
                    ProcedureTagStock.production_item_id == production_item.id,
                    ProcedureTagStock.flow_node_id == flow_node_id,
                    ProcedureTagStock.source_flow_node_id == source_flow_node_id,
                    ProcedureTagStock.department_id == department.id,
                )
            ).all()
        )
        stocks_by_set = {stock.tag_set_id: stock for stock in stocks}
        all_orders = list(
            session.scalars(
                select(WorkOrder)
                .where(
                    WorkOrder.production_item_id == production_item.id,
                    WorkOrder.flow_node_id == flow_node_id,
                    WorkOrder.source_flow_node_id == source_flow_node_id,
                    WorkOrder.work_order_type == "tag",
                )
                .order_by(WorkOrder.id)
            ).all()
        )
        open_by_target: dict[int, list[WorkOrder]] = defaultdict(list)
        for order in all_orders:
            if order.status == "open" and order.target_tag_set_id is not None:
                open_by_target[order.target_tag_set_id].append(order)
        batches = list(
            session.scalars(
                select(WorkOrderBatch).where(
                    WorkOrderBatch.work_order_id.in_([order.id for order in all_orders])
                )
            ).all()
        ) if all_orders else []
        orders_by_id = {order.id: order for order in all_orders}
        pending_by_target: dict[int, int] = defaultdict(int)
        rework_resubmitted_by_batch: dict[int, int] = defaultdict(int)
        for batch in batches:
            if batch.rework_source_batch_id is not None:
                rework_resubmitted_by_batch[batch.rework_source_batch_id] += (
                    batch.submitted_quantity
                )
            order = orders_by_id[batch.work_order_id]
            if batch.recorded_at is not None:
                continue
            if order.target_tag_set_id is not None:
                pending_by_target[order.target_tag_set_id] += batch.submitted_quantity
        rework_pending_by_order: dict[int, int] = defaultdict(int)
        for batch in batches:
            if batch.recorded_at is not None:
                rework_pending_by_order[batch.work_order_id] += max(
                    (batch.rework_quantity or 0)
                    - rework_resubmitted_by_batch.get(batch.id, 0),
                    0,
                )

        evidenced_orders = [order for order in all_orders if order.status != "cancelled"]
        used_set_ids = set(stocks_by_set) | set(pending_by_target)
        used_set_ids.update(
            tag_set_id
            for order in evidenced_orders
            for tag_set_id in (order.source_tag_set_id, order.target_tag_set_id)
            if tag_set_id is not None
        )
        valid_set_ids = set(
            session.scalars(
                select(ProcedureTagSet.id).where(
                    ProcedureTagSet.procedure_id == procedure.id,
                    ProcedureTagSet.id.in_(used_set_ids),
                )
            ).all()
        ) if used_set_ids else set()
        first_order_id: dict[int, int] = {}
        for order in evidenced_orders:
            if order.target_tag_set_id is not None:
                first_order_id.setdefault(order.target_tag_set_id, order.id)

        repository_reserved = (
            reserved_quantities(session, [repository.id]).get(repository.id, 0)
            if repository else 0
        )
        repository_available = max(
            (repository.quantity if repository else 0) - repository_reserved,
            0,
        )
        cards = [{
            "card_key": f"untagged:{production_item.id}:{flow_node_id}:{source_flow_node_id}",
            "production_item_id": production_item.id,
            "flow_node_id": flow_node_id,
            "source_flow_node_id": source_flow_node_id,
            "procedure_id": procedure.id,
            "tag_set_id": None,
            "tag_ids": [],
            "tag_names": [],
            "tag_set_name": "未打标记",
            "repository_id": repository.id if repository else None,
            "tag_stock_id": None,
            "available_quantity": repository_available,
            "processing_quantity": 0,
            "pending_qc_quantity": 0,
            "completed_quantity": repository_available,
        }]
        reserved_by_stock = reserved_tag_quantities(session, [stock.id for stock in stocks])
        ordered_set_ids = sorted(
            valid_set_ids,
            key=lambda tag_set_id: (first_order_id.get(tag_set_id, 2**63 - 1), tag_set_id),
        )
        for tag_set_id in ordered_set_ids:
            stock = stocks_by_set.get(tag_set_id)
            completed = max(
                (stock.quantity if stock else 0)
                - (reserved_by_stock.get(stock.id, 0) if stock else 0),
                0,
            )
            processing = sum(
                max(order.quantity - order.completed_quantity, 0)
                + rework_pending_by_order.get(order.id, 0)
                for order in open_by_target.get(tag_set_id, [])
            )
            cards.append({
                "card_key": f"tag-set:{tag_set_id}",
                "production_item_id": production_item.id,
                "flow_node_id": flow_node_id,
                "source_flow_node_id": source_flow_node_id,
                "procedure_id": procedure.id,
                **serialize_tag_set(session, tag_set_id),
                "repository_id": None,
                "tag_stock_id": stock.id if stock else None,
                "available_quantity": completed,
                "processing_quantity": processing,
                "pending_qc_quantity": pending_by_target.get(tag_set_id, 0),
                "completed_quantity": completed,
            })
        return cards
