from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from models.organization import Department, Procedure, ProcedureSubstep, Worker, Workshop
from models.production import (
    ProcedureStageStock,
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from services.errors import DomainError
from services.production_card_status import reserved_quantities, reserved_stage_quantities
from services.production_flow import load_production_flow


def list_substep_cards(
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
            or workshop is None
            or workshop.department_id != department.id
            or procedure.procedure_type != "standard"
        ):
            raise DomainError(
                "substep_cards_not_available",
                "当前配件位置不支持细分工序卡片",
            )

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
                select(ProcedureStageStock).where(
                    ProcedureStageStock.production_item_id == production_item.id,
                    ProcedureStageStock.flow_node_id == flow_node_id,
                    ProcedureStageStock.source_flow_node_id == source_flow_node_id,
                    ProcedureStageStock.department_id == department.id,
                )
            ).all()
        )
        stocks_by_substep = {stock.completed_substep_id: stock for stock in stocks}

        all_orders = list(
            session.scalars(
                select(WorkOrder)
                .where(
                    WorkOrder.production_item_id == production_item.id,
                    WorkOrder.flow_node_id == flow_node_id,
                    WorkOrder.source_flow_node_id == source_flow_node_id,
                    WorkOrder.work_order_type == "substep",
                )
                .order_by(WorkOrder.id)
            ).all()
        )
        open_orders = [order for order in all_orders if order.status == "open"]
        open_orders_by_substep: dict[int, list[WorkOrder]] = defaultdict(list)
        for order in open_orders:
            if order.substep_id is not None:
                open_orders_by_substep[order.substep_id].append(order)

        pending_rows = session.execute(
            select(WorkOrderBatch, WorkOrder)
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(
                WorkOrder.production_item_id == production_item.id,
                WorkOrder.flow_node_id == flow_node_id,
                WorkOrder.work_order_type == "substep",
                WorkOrderBatch.source_flow_node_id == source_flow_node_id,
                WorkOrderBatch.recorded_at.is_(None),
            )
        ).all()
        pending_by_substep: dict[int, int] = defaultdict(int)
        for batch, order in pending_rows:
            if order.substep_id is not None:
                pending_by_substep[order.substep_id] += batch.submitted_quantity

        evidenced_orders = [
            order for order in all_orders if order.status != "cancelled"
        ]
        used_substep_ids = {
            order.substep_id
            for order in evidenced_orders
            if order.substep_id is not None
        }
        used_substep_ids.update(stocks_by_substep)
        used_substep_ids.update(pending_by_substep)
        used_substep_ids.update(
            batch.source_substep_id
            for batch, _ in pending_rows
            if batch.source_substep_id is not None
        )
        substeps = {
            item.id: item
            for item in session.scalars(
                select(ProcedureSubstep).where(
                    ProcedureSubstep.procedure_id == procedure.id,
                    ProcedureSubstep.id.in_(used_substep_ids),
                )
            ).all()
        } if used_substep_ids else {}
        first_order_id: dict[int, int] = {}
        for order in evidenced_orders:
            if order.substep_id is not None:
                first_order_id.setdefault(order.substep_id, order.id)

        repository_reserved = (
            reserved_quantities(session, [repository.id]).get(repository.id, 0)
            if repository
            else 0
        )
        stage_reserved = reserved_stage_quantities(
            session,
            [stock.id for stock in stocks],
        )
        cards = [
            {
                "card_key": f"unprocessed:{production_item.id}:{flow_node_id}:{source_flow_node_id}",
                "production_item_id": production_item.id,
                "flow_node_id": flow_node_id,
                "source_flow_node_id": source_flow_node_id,
                "procedure_id": procedure.id,
                "substep_id": None,
                "substep_name": f"未{procedure.procedure_name}",
                "repository_id": repository.id if repository else None,
                "stage_stock_id": None,
                "available_quantity": max(
                    (repository.quantity if repository else 0) - repository_reserved,
                    0,
                ),
                "processing_quantity": 0,
                "pending_qc_quantity": 0,
                "completed_quantity": 0,
                "can_create_work_order": bool(
                    repository and repository.quantity > repository_reserved
                ),
                "can_submit_qc": False,
                "open_work_orders": [],
            }
        ]
        ordered_substeps = sorted(
            substeps.values(),
            key=lambda item: (first_order_id.get(item.id, 2**63 - 1), item.id),
        )
        for substep in ordered_substeps:
            stock = stocks_by_substep.get(substep.id)
            completed_quantity = max(
                (stock.quantity if stock else 0)
                - (stage_reserved.get(stock.id, 0) if stock else 0),
                0,
            )
            summaries = [
                _serialize_open_order(session, order)
                for order in open_orders_by_substep.get(substep.id, [])
            ]
            processing_quantity = sum(
                item["processing_quantity"] for item in summaries
            )
            cards.append(
                {
                    "card_key": f"substep:{substep.id}",
                    "production_item_id": production_item.id,
                    "flow_node_id": flow_node_id,
                    "source_flow_node_id": source_flow_node_id,
                    "procedure_id": procedure.id,
                    "substep_id": substep.id,
                    "substep_name": substep.substep_name,
                    "repository_id": None,
                    "stage_stock_id": stock.id if stock else None,
                    "available_quantity": completed_quantity,
                    "processing_quantity": processing_quantity,
                    "pending_qc_quantity": pending_by_substep.get(substep.id, 0),
                    "completed_quantity": completed_quantity,
                    "can_create_work_order": completed_quantity > 0,
                    "can_submit_qc": processing_quantity > 0,
                    "open_work_orders": summaries,
                }
            )
        return cards


def _serialize_open_order(session, order: WorkOrder) -> dict:
    worker = session.get(Worker, order.worker_id) if order.worker_id else None
    return {
        "id": order.id,
        "work_order_no": order.work_order_no,
        "worker_id": order.worker_id,
        "worker_name": worker.worker_name if worker else None,
        "quantity": order.quantity,
        "processing_quantity": max(order.quantity - order.completed_quantity, 0),
    }
