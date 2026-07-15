from sqlalchemy import select

from database import SessionLocal
from domain.time import utc_now
from models.organization import Department, Worker
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch
from schemas.production import QcInspection
from services.errors import DomainError
from services.production_movements import record_movement
from services.work_order_presenters import serialize_batch
from services.work_order_support import (
    consume_repository,
    move_to_node,
    node_context,
    refresh_order_closed,
    target_department_id,
)


def inspect_batch(
    batch_id: int,
    payload: QcInspection,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "qc"}:
        raise DomainError("qc_access_denied", "只有 QC 可以录入质检结果", status_code=403)
    with SessionLocal.begin() as session:
        qc_department = session.scalar(
            select(Department).where(Department.department_code == "qc")
        )
        qc_worker = session.get(Worker, payload.qc_worker_id)
        if (
            qc_department is None
            or qc_worker is None
            or qc_worker.department_id != qc_department.id
        ):
            raise DomainError("qc_worker_invalid", "请选择有效的 QC 工人")

        batch = session.get(WorkOrderBatch, batch_id)
        if batch is None:
            raise DomainError("qc_batch_not_found", "送检批次不存在", status_code=404)
        # Keep the same lock order as movement validation: work order, then batch.
        order = session.get(WorkOrder, batch.work_order_id, with_for_update=True)
        session.refresh(batch, with_for_update=True)
        if order is None or batch.work_order_id != order.id:
            raise DomainError("qc_batch_not_found", "送检批次所属工单不存在", status_code=404)
        if batch.recorded_at is not None:
            raise DomainError("qc_batch_completed", "该批次已经完成质检")
        total = _inspection_total(payload)
        if total != batch.submitted_quantity:
            raise DomainError("qc_quantity_mismatch", "质检结果合计必须等于送检数量")
        if total - payload.qualified_quantity > 0 and not (payload.defect_reason or "").strip():
            raise DomainError("defect_reason_required", "存在异常数量时必须填写不良原因")

        production_item = session.get(
            ProductionItem, order.production_item_id, with_for_update=True
        )
        context, qc_node = node_context(session, production_item, batch.flow_node_id)
        qc_department_id = target_department_id(session, qc_node)
        qc_repository = session.scalar(
            select(Repository)
            .where(
                Repository.production_item_id == production_item.id,
                Repository.flow_node_id == batch.flow_node_id,
                Repository.source_flow_node_id == order.flow_node_id,
                Repository.department_id == qc_department_id,
            )
            .with_for_update()
        )
        if qc_repository is None or qc_repository.quantity < total:
            raise DomainError("qc_repository_quantity_invalid", "QC 配件数量不足")

        approved = context.normal_target(qc_node["id"])
        rework_targets = [
            context.nodes.get(edge.get("target_node_id"))
            for edge in context.flow.get("edges", [])
            if edge.get("source_node_id") == qc_node["id"]
            and edge.get("route_type") == "rework"
        ]
        rework_targets = [item for item in rework_targets if item is not None]
        if payload.rework_quantity and len(rework_targets) != 1:
            raise DomainError("rework_target_missing", "QC 返工数量缺少唯一返工目标")

        _move_inspection_result(
            session,
            production_item,
            order,
            batch,
            qc_node,
            approved,
            payload.qualified_quantity,
            "qc_qualified",
            qc_department_id,
        )
        if payload.rework_quantity:
            _move_inspection_result(
                session,
                production_item,
                order,
                batch,
                qc_node,
                rework_targets[0],
                payload.rework_quantity,
                "qc_rework",
                qc_department_id,
            )
        _record_loss(
            session,
            production_item,
            order,
            batch,
            qc_node,
            payload.scrap_quantity,
            "scrap",
            qc_department_id,
        )
        _record_loss(
            session,
            production_item,
            order,
            batch,
            qc_node,
            payload.lost_quantity,
            "lost",
            qc_department_id,
        )
        # Persist result movements before completing the batch so the database
        # can verify the recorded QC totals against immutable movement history.
        session.flush()
        consume_repository(session, qc_repository, total)
        _complete_batch(batch, payload, qc_worker)
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_batch(batch)


def _inspection_total(payload: QcInspection) -> int:
    return sum(
        (
            payload.qualified_quantity,
            payload.rework_quantity,
            payload.scrap_quantity,
            payload.lost_quantity,
        )
    )


def _move_inspection_result(
    session,
    production_item,
    order,
    batch,
    qc_node,
    target,
    quantity,
    movement_type,
    qc_department_id,
) -> None:
    target_department = move_to_node(
        session, production_item, target, quantity, qc_node["id"]
    )
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type=movement_type,
        source_flow_node_id=qc_node["id"],
        target_flow_node_id=target.get("id") if target else None,
        source_department_id=qc_department_id,
        target_department_id=target_department,
        work_order_id=order.id,
        work_order_batch_id=batch.id,
    )


def _record_loss(
    session,
    production_item,
    order,
    batch,
    qc_node,
    quantity,
    movement_type,
    qc_department_id,
) -> None:
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type=movement_type,
        source_flow_node_id=qc_node["id"],
        target_flow_node_id=None,
        source_department_id=qc_department_id,
        work_order_id=order.id,
        work_order_batch_id=batch.id,
    )


def _complete_batch(batch, payload: QcInspection, worker: Worker) -> None:
    batch.qualified_quantity = payload.qualified_quantity
    batch.rework_quantity = payload.rework_quantity
    batch.scrap_quantity = payload.scrap_quantity
    batch.lost_quantity = payload.lost_quantity
    batch.qc_worker_id = worker.id
    batch.qc_worker_name = worker.worker_name
    batch.defect_reason = (payload.defect_reason or "").strip() or None
    batch.recorded_at = utc_now()
