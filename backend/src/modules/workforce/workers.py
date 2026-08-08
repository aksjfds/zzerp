from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, business_iso
from modules.engineering.product_reference_api import get_product_reference
from modules.errors import DomainError
from modules.organization.read_api import (
    DepartmentView,
    WorkshopView,
    get_department_views_by_codes,
    get_workshop_views,
)
from modules.production_core.operational_api import calculate_work_order_progress
from modules.production_core.workforce_api import (
    WorkOrderActivity,
    get_production_item_display,
    list_work_order_activities,
    list_worker_activity_orders,
)
from modules.quality.workforce_api import (
    WorkOrderBatchActivity,
    list_batch_activities,
    list_qualified_batch_order_ids,
    list_qc_worker_order_ids,
)
from modules.standard_execution.pay_reference_api import (
    PayDetailView,
    list_pay_details,
)
from modules.workforce.persistence import Worker


PRODUCTION_DEPARTMENT_CODES = (
    "stamp",
    "cnc",
    "polish",
    "outsource",
    "purchasing",
    "qc",
    "assembly",
)


def worker_overview() -> list[dict]:
    with SessionLocal() as session:
        departments = get_department_views_by_codes(
            session,
            PRODUCTION_DEPARTMENT_CODES,
        )
        workshops = {
            item.id: item
            for item in get_workshop_views(
                session,
                department_ids={item.id for item in departments},
            )
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


def department_worker_overview(department_code: str) -> dict:
    with SessionLocal() as session:
        department = _production_department(session, department_code)
        workshops = get_workshop_views(
            session,
            department_ids={department.id},
        )
        workshop_by_id = {item.id: item for item in workshops}
        workers = session.scalars(
            select(Worker)
            .where(Worker.department_id == department.id)
            .order_by(Worker.worker_name, Worker.id)
        ).all()
        return {
            "department_id": department.id,
            "department_name": department.department_name,
            "department_code": department.department_code,
            "workshops": workshops,
            "workers": [
                _serialize_worker(
                    department,
                    worker,
                    workshop_by_id.get(worker.workshop_id),
                )
                for worker in workers
            ],
        }


def list_department_workers(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        department = _production_department(session, department_code)
        return [
            {
                "id": worker.id,
                "worker_name": worker.worker_name,
                "department_id": worker.department_id,
                "workshop_id": worker.workshop_id,
            }
            for worker in session.scalars(
                select(Worker)
                .where(Worker.department_id == department.id)
                .order_by(Worker.worker_name, Worker.id)
            )
        ]


def create_department_worker(
    department_code: str,
    worker_name: str,
    workshop_id: int | None,
) -> dict:
    normalized_name = worker_name.strip()
    with SessionLocal.begin() as session:
        department = _production_department(session, department_code)
        department_workshops = get_workshop_views(
            session,
            department_ids={department.id},
        )
        workshops_by_id = {item.id: item for item in department_workshops}
        workshop = workshops_by_id.get(workshop_id) if workshop_id else None
        department_has_workshops = bool(department_workshops)
        if department_has_workshops and workshop_id is None:
            raise DomainError("worker_workshop_required", "请选择工人所属车间")
        if workshop_id and (
            workshop is None or workshop.department_id != department.id
        ):
            raise DomainError("worker_workshop_invalid", "所选车间不属于当前部门")
        existing = session.scalar(
            select(Worker.id).where(
                Worker.department_id == department.id,
                Worker.workshop_id == workshop_id,
                Worker.worker_name == normalized_name,
            ).limit(1)
        )
        if existing is not None:
            raise DomainError("worker_already_exists", "当前部门和车间已存在同名工人")
        worker = Worker(
            worker_name=normalized_name,
            department_id=department.id,
            workshop_id=workshop_id,
        )
        session.add(worker)
        session.flush()
        return _serialize_worker(department, worker, workshop)


def worker_history(
    worker_id: int,
    month: str,
    department_code: str | None = None,
) -> list[dict]:
    with SessionLocal() as session:
        worker = session.get(Worker, worker_id)
        if worker is None:
            return []
        if department_code is not None:
            department = _production_department(session, department_code)
            if worker.department_id != department.id:
                raise DomainError(
                    "worker_department_mismatch",
                    "工人不属于当前部门",
                    status_code=404,
                )

        month_start, month_end = _month_bounds(month)
        work_orders = list_worker_activity_orders(
            session,
            worker_id,
            month_start,
            month_end,
        )
        qc_order_ids = list_qc_worker_order_ids(
            session,
            worker.id,
            month_start,
            month_end,
        )
        if qc_order_ids:
            existing_ids = {item.id for item in work_orders}
            work_orders.extend(
                item
                for item in list_work_order_activities(session, qc_order_ids)
                if item.id not in existing_ids
            )

        if not work_orders:
            return []

        batch_map: dict[int, list[WorkOrderBatchActivity]] = defaultdict(list)
        for batch in list_batch_activities(
            session,
            {item.id for item in work_orders},
        ):
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


def worker_pay_summary(
    worker_id: int,
    month: str,
    department_code: str | None = None,
) -> dict:
    with SessionLocal() as session:
        worker = session.get(Worker, worker_id)
        if worker is None:
            return _empty_pay_summary(worker_id, month)
        if department_code is not None:
            department = _production_department(session, department_code)
            if worker.department_id != department.id:
                raise DomainError(
                    "worker_department_mismatch",
                    "工人不属于当前部门",
                    status_code=404,
                )

        month_start, month_end = _month_bounds(month)
        monthly_order_ids = list_qualified_batch_order_ids(
            session,
            month_start,
            month_end,
        )
        candidate_orders = list_work_order_activities(
            session,
            monthly_order_ids,
            worker_id=worker_id,
            work_order_type="tag",
        )
        orders_by_id = {item.id: item for item in candidate_orders}
        batches = list_batch_activities(
            session,
            set(orders_by_id),
            month_start=month_start,
            month_end=month_end,
            qualified_only=True,
        )
        batch_rows = [
            (batch, orders_by_id[batch.work_order_id])
            for batch in batches
            if batch.work_order_id in orders_by_id
        ]
        if not batch_rows:
            return _empty_pay_summary(worker_id, month)

        order_ids = {order.id for _, order in batch_rows}
        pay_details_by_order: dict[int, list[PayDetailView]] = defaultdict(list)
        for detail in list_pay_details(session, order_ids):
            pay_details_by_order[detail.work_order_id].append(detail)

        groups: dict[tuple, dict] = {}
        total_quantity = 0
        total_pay = Decimal("0")
        unpriced_quantity = 0
        for batch, order in batch_rows:
            quantity = batch.qualified_quantity or 0
            total_quantity += quantity
            details = pay_details_by_order.get(order.id, [])
            unit_price = (
                sum((item.unit_price for item in details), Decimal("0"))
                if details else None
            )
            tag_names = tuple(item.tag_name for item in details)
            item_name = _worker_item_name(session, order)
            key = (
                order.production_item_id,
                order.procedure_id,
                tag_names,
                unit_price,
            )
            group = groups.setdefault(key, {
                "item_name": item_name,
                "procedure_name": order.work_order_name,
                "tag_names": list(tag_names),
                "qualified_quantity": 0,
                "unit_price": unit_price,
                "pay_amount": Decimal("0") if unit_price is not None else None,
            })
            group["qualified_quantity"] += quantity
            if unit_price is None:
                unpriced_quantity += quantity
            else:
                amount = unit_price * quantity
                group["pay_amount"] += amount
                total_pay += amount

        items = list(groups.values())
        return {
            "worker_id": worker_id,
            "month": month,
            "qualified_quantity": total_quantity,
            "total_pay": total_pay,
            "unpriced_quantity": unpriced_quantity,
            "items": items,
        }


def _empty_pay_summary(worker_id: int, month: str) -> dict:
    return {
        "worker_id": worker_id,
        "month": month,
        "qualified_quantity": 0,
        "total_pay": Decimal("0"),
        "unpriced_quantity": 0,
        "items": [],
    }


def _serialize_worker(
    department: DepartmentView,
    worker: Worker,
    workshop: WorkshopView | None,
) -> dict:
    return {
        "id": worker.id,
        "worker_name": worker.worker_name,
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "workshop_id": worker.workshop_id,
        "workshop_name": workshop.workshop_name if workshop else None,
    }


def _production_department(session, department_code: str) -> DepartmentView:
    if department_code not in PRODUCTION_DEPARTMENT_CODES:
        raise DomainError("department_not_found", "生产部门不存在", status_code=404)
    department = next(
        iter(get_department_views_by_codes(session, {department_code})),
        None,
    )
    if department is None:
        raise DomainError("department_not_found", "生产部门不存在", status_code=404)
    return department


def _serialize_history_item(
    session,
    worker: Worker,
    order: WorkOrderActivity,
    batches: list[WorkOrderBatchActivity],
) -> dict:
    production_item = get_production_item_display(
        session,
        order.production_item_id,
    )
    item_name = production_item.item_name if production_item else "未知配件"
    product = get_product_reference(session, production_item.product_id) if production_item else None
    if product is not None:
        item_name = f"{product.factory_code}-{product.product_name}-{item_name}"
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


def _worker_item_name(session, order: WorkOrderActivity) -> str:
    production_item = get_production_item_display(
        session,
        order.production_item_id,
    )
    if production_item is None:
        return "未知配件"
    item_name = production_item.item_name
    product = get_product_reference(session, production_item.product_id)
    return (
        f"{product.factory_code}-{product.product_name}-{item_name}"
        if product is not None else item_name
    )


def _history_date_for_worker(
    worker: Worker,
    order: WorkOrderActivity,
    worker_batches: list[WorkOrderBatchActivity],
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
