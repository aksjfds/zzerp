from sqlalchemy import exists, func, or_, select

from database import SessionLocal
from models.organization import Department, Procedure, Worker, Workshop
from models.production import WorkOrder, WorkOrderBatch, WorkOrderMaterial
from services.errors import DomainError
from services.work_order_presenters import (
    item_display,
    serialize_batch,
    serialize_work_order,
    work_order_context,
)


def list_department_work_orders(
    department_code: str,
    page: int,
    page_size: int,
    production_item_id: int | None = None,
    flow_node_id: str | None = None,
    target_tag_set_id: int | None = None,
    source_flow_node_id: str | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = _department(session, department_code)
        statement = (
            select(WorkOrder)
            .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
            .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
            .order_by(WorkOrder.id.desc())
        )
        condition = (
            WorkOrder.work_order_type == "assembly"
            if department_code == "assembly"
            else (
                (WorkOrder.work_order_type.in_(("tag", "purchase_receipt")))
                & (Workshop.department_id == department.id)
            )
        )
        if production_item_id is not None:
            condition = condition & _related_to_production_item(production_item_id)
        if flow_node_id is not None:
            condition = condition & (WorkOrder.flow_node_id == flow_node_id)
        if source_flow_node_id is not None:
            condition = condition & (
                WorkOrder.source_flow_node_id == source_flow_node_id
            )
        if target_tag_set_id is not None:
            condition = condition & (WorkOrder.target_tag_set_id == target_tag_set_id)
        filtered = statement.where(condition)
        total = session.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        ) or 0
        orders = session.scalars(
            filtered.offset((page - 1) * page_size).limit(page_size)
        ).all()
        _cache_order_relations(session, [order.id for order in orders])
        return [serialize_work_order(session, item) for item in orders], total


def list_department_workers(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        department = _department(session, department_code)
        workers = session.scalars(
            select(Worker)
            .where(Worker.department_id == department.id)
            .order_by(Worker.worker_name, Worker.id)
        ).all()
        return [
            {
                "id": worker.id,
                "worker_name": worker.worker_name,
                "department_id": worker.department_id,
                "workshop_id": worker.workshop_id,
            }
            for worker in workers
        ]


def list_qc_batches(
    page: int,
    page_size: int,
    production_item_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        statement = select(WorkOrderBatch).join(
            WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id
        ).where(WorkOrderBatch.recorded_at.is_(None))
        if production_item_id is not None:
            statement = statement.where(_related_to_production_item(production_item_id))
        total = session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0
        batches = session.scalars(
            statement
            .order_by(WorkOrderBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [_serialize_pending_batch(session, batch) for batch in batches], total


def _department(session, department_code: str) -> Department:
    department = session.scalar(
        select(Department).where(Department.department_code == department_code)
    )
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    return department


def _related_to_production_item(production_item_id: int):
    return or_(
        WorkOrder.production_item_id == production_item_id,
        exists(
            select(WorkOrderMaterial.id).where(
                WorkOrderMaterial.work_order_id == WorkOrder.id,
                WorkOrderMaterial.production_item_id == production_item_id,
            )
        ),
    )


def _cache_order_relations(session, order_ids: list[int]) -> None:
    batch_cache: dict[int, list[WorkOrderBatch]] = {}
    material_cache: dict[int, list[int]] = {}
    if order_ids:
        for batch in session.scalars(
            select(WorkOrderBatch)
            .where(WorkOrderBatch.work_order_id.in_(order_ids))
            .order_by(WorkOrderBatch.id)
        ):
            batch_cache.setdefault(batch.work_order_id, []).append(batch)
        for work_order_id, production_item_id in session.execute(
            select(
                WorkOrderMaterial.work_order_id,
                WorkOrderMaterial.production_item_id,
            ).where(WorkOrderMaterial.work_order_id.in_(order_ids))
        ):
            material_cache.setdefault(work_order_id, []).append(production_item_id)
    session.info["work_order_batch_cache"] = batch_cache
    session.info["work_order_material_cache"] = material_cache


def _serialize_pending_batch(session, batch: WorkOrderBatch) -> dict:
    order = session.get(WorkOrder, batch.work_order_id)
    customer_order, _, production_item = work_order_context(session, order)
    part_no, part_name = item_display(session, production_item)
    data = serialize_batch(batch)
    data.update(
        {
            "repository_id": order.repository_id,
            "production_item_id": order.production_item_id,
            "work_order_no": order.work_order_no,
            "customer_order_no": customer_order.customer_order_no,
            "part_no": part_no,
            "part_name": part_name,
            "work_order_name": order.work_order_name,
            "remaining_quantity": batch.submitted_quantity,
        }
    )
    return data
