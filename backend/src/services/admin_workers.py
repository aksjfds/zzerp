from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, business_iso
from models.organization import Department, Worker, Workshop
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.work_order_presenters import item_display
from services.work_order_progress import calculate_work_order_progress


PRODUCTION_DEPARTMENT_CODES = ("stamp", "polish", "qc", "assembly", "warehouse")


def worker_overview() -> list[dict]:
    with SessionLocal() as session:
        departments = session.scalars(
            select(Department)
            .where(Department.department_code.in_(PRODUCTION_DEPARTMENT_CODES))
            .order_by(Department.id)
        ).all()
        workshops = {
            item.id: item
            for item in session.scalars(select(Workshop)).all()
        }
        workers_by_department: dict[int, list[Worker]] = defaultdict(list)
        for worker in session.scalars(
            select(Worker)
            .where(Worker.department_id.in_([item.id for item in departments]))
            .order_by(Worker.worker_name, Worker.id)
        ).all():
            workers_by_department[worker.department_id].append(worker)

        return [
            {
                "department_id": department.id,
                "department_name": department.department_name,
                "department_code": department.department_code,
                "workers": [
                    _serialize_worker(department, worker, workshops.get(worker.workshop_id))
                    for worker in workers_by_department.get(department.id, [])
                ],
            }
            for department in departments
        ]


def worker_history(worker_id: int, month: str) -> list[dict]:
    with SessionLocal() as session:
        worker = session.get(Worker, worker_id)
        if worker is None:
            return []

        month_start, month_end = _month_bounds(month)
        work_orders = session.scalars(
            select(WorkOrder)
            .where(
                WorkOrder.worker_id == worker_id,
                func.coalesce(WorkOrder.closed_at, WorkOrder.created_at) >= month_start,
                func.coalesce(WorkOrder.closed_at, WorkOrder.created_at) < month_end,
            )
            .order_by(
                func.coalesce(WorkOrder.closed_at, WorkOrder.created_at).desc(),
                WorkOrder.id.desc(),
            )
        ).all()
        qc_order_ids = [
            row[0]
            for row in session.execute(
                select(WorkOrderBatch.work_order_id)
                .where(
                    WorkOrderBatch.qc_worker_id == worker.id,
                    WorkOrderBatch.recorded_at >= month_start,
                    WorkOrderBatch.recorded_at < month_end,
                )
                .distinct()
            ).all()
        ]
        if qc_order_ids:
            existing_ids = {item.id for item in work_orders}
            work_orders.extend(
                item
                for item in session.scalars(
                    select(WorkOrder).where(WorkOrder.id.in_(qc_order_ids))
                ).all()
                if item.id not in existing_ids
            )

        if not work_orders:
            return []

        batch_map: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        for batch in session.scalars(
            select(WorkOrderBatch)
            .where(WorkOrderBatch.work_order_id.in_([item.id for item in work_orders]))
            .order_by(WorkOrderBatch.id)
        ).all():
            batch_map[batch.work_order_id].append(batch)

        result = []
        for order in work_orders:
            order_batches = batch_map.get(order.id, [])
            worker_batches = [
                item for item in order_batches if item.qc_worker_id == worker.id
            ]
            date_for_range = _history_date_for_worker(worker, order, worker_batches)
            if date_for_range < month_start or date_for_range >= month_end:
                continue
            result.append(_serialize_history_item(session, worker, order, order_batches))
        return sorted(
            result,
            key=lambda item: item["completed_at"] or "",
            reverse=True,
        )


def _serialize_worker(department: Department, worker: Worker, workshop: Workshop | None) -> dict:
    return {
        "id": worker.id,
        "worker_name": worker.worker_name,
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "workshop_id": worker.workshop_id,
        "workshop_name": workshop.workshop_name if workshop else None,
    }


def _serialize_history_item(
    session,
    worker: Worker,
    order: WorkOrder,
    batches: list[WorkOrderBatch],
) -> dict:
    production_item = session.get(ProductionItem, order.production_item_id)
    _, item_name = item_display(session, production_item) if production_item else ("", "未知配件")
    worker_batches = [
        item for item in batches if item.qc_worker_id == worker.id
    ]
    progress = calculate_work_order_progress(order, batches)
    if worker_batches and order.worker_id != worker.id:
        completed_quantity = sum(item.submitted_quantity for item in worker_batches)
        planned_quantity = completed_quantity
        procedure_name = "QC"
        status = "closed"
        completed_at = _history_date_for_worker(worker, order, worker_batches)
    else:
        completed_quantity = progress.submitted_quantity
        planned_quantity = order.quantity
        procedure_name = order.work_order_name
        status = order.status
        completed_at = order.closed_at or order.created_at
    lost_quantity = sum(item.lost_quantity or 0 for item in worker_batches or batches)
    scrap_quantity = sum(item.scrap_quantity or 0 for item in worker_batches or batches)
    rework_pending = (
        progress.rework_pending_quantity
        if order.work_order_type == "tag" and order.worker_id == worker.id else 0
    )
    return {
        "work_order_id": order.id,
        "work_order_no": order.work_order_no,
        "item_name": item_name,
        "procedure_name": procedure_name,
        "planned_quantity": planned_quantity,
        "completed_quantity": completed_quantity,
        "processing_quantity": (
            progress.initial_processing_quantity + rework_pending
            if order.worker_id == worker.id
            else max(planned_quantity - completed_quantity, 0)
        ),
        "completion_rate": round(completed_quantity / planned_quantity, 4)
        if planned_quantity else 0,
        "lost_quantity": lost_quantity,
        "scrap_quantity": scrap_quantity,
        "status": status,
        "completed_at": business_iso(completed_at),
    }


def _history_date_for_worker(
    worker: Worker,
    order: WorkOrder,
    worker_batches: list[WorkOrderBatch],
) -> datetime:
    if worker_batches and order.worker_id != worker.id:
        return max(
            (item.recorded_at for item in worker_batches if item.recorded_at),
            default=order.closed_at or order.created_at,
        )
    return order.closed_at or order.created_at


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    try:
        year, month_number = (int(item) for item in month.split("-", 1))
        start = datetime(year, month_number, 1, tzinfo=BUSINESS_TIMEZONE)
    except ValueError as exc:
        raise ValueError("月份格式不正确") from exc
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=BUSINESS_TIMEZONE)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=BUSINESS_TIMEZONE)
    return start, end
