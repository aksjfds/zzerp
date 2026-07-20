from sqlalchemy import select

from database import SessionLocal
from domain.time import utc_now
from models.organization import Department, Procedure, Worker
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from schemas.production import QcInspection
from services.errors import DomainError
from services import purchase_qc_routing, tag_qc_routing
from services.production_movements import record_movement
from services.work_order_presenters import serialize_batch
from services.work_order_support import node_context, refresh_order_closed


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
        order = session.get(WorkOrder, batch.work_order_id, with_for_update=True)
        session.refresh(batch, with_for_update=True)
        if order is None or batch.work_order_id != order.id:
            raise DomainError("qc_batch_not_found", "送检批次所属工单不存在", status_code=404)
        if batch.recorded_at is not None:
            raise DomainError("qc_batch_completed", "该批次已经完成质检")
        if order.work_order_type not in {"tag", "purchase_receipt"}:
            raise DomainError("qc_work_order_type_invalid", "当前工单不支持送 QC")
        if order.work_order_type == "tag" and order.status != "open":
            raise DomainError("work_order_closed", "生产工单已经结单")

        total = _inspection_total(payload)
        if total != batch.submitted_quantity:
            raise DomainError("qc_quantity_mismatch", "质检结果合计必须等于送检数量")
        if total - payload.qualified_quantity > 0 and not (payload.defect_reason or "").strip():
            raise DomainError("defect_reason_required", "存在异常数量时必须填写不良原因")

        production_item = session.get(
            ProductionItem,
            order.production_item_id,
            with_for_update=True,
        )
        if production_item is None:
            raise DomainError("production_context_missing", "送检工单的生产资料不完整")
        context, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None or order.procedure_id != procedure.id:
            raise DomainError("production_context_missing", "送检工单的工艺资料不完整")
        routing = (
            tag_qc_routing
            if order.work_order_type == "tag"
            else purchase_qc_routing
        )
        routing.validate_context(session, order, procedure)

        if payload.qualified_quantity:
            target_node_id, target_department_id = routing.route_qualified(
                session,
                order=order,
                batch=batch,
                production_item=production_item,
                procedure=procedure,
                context=context,
                node=node,
                quantity=payload.qualified_quantity,
            )
            record_movement(
                session,
                production_item=production_item,
                quantity=payload.qualified_quantity,
                movement_type="qc_qualified",
                source_flow_node_id=node["id"],
                target_flow_node_id=target_node_id,
                source_tag_set_id=order.target_tag_set_id,
                target_tag_set_id=order.target_tag_set_id,
                source_department_id=qc_department.id,
                target_department_id=target_department_id,
                work_order_id=order.id,
                work_order_batch_id=batch.id,
            )

        if payload.rework_quantity:
            target_department_id = routing.route_rework(
                session,
                order=order,
                batch=batch,
                production_item=production_item,
                procedure=procedure,
                node=node,
                quantity=payload.rework_quantity,
            )
            record_movement(
                session,
                production_item=production_item,
                quantity=payload.rework_quantity,
                movement_type="qc_rework",
                source_flow_node_id=node["id"],
                target_flow_node_id=node["id"],
                source_tag_set_id=order.target_tag_set_id,
                target_tag_set_id=order.source_tag_set_id,
                source_department_id=qc_department.id,
                target_department_id=target_department_id,
                work_order_id=order.id,
                work_order_batch_id=batch.id,
            )

        _record_loss(
            session,
            production_item,
            order,
            batch,
            node["id"],
            payload.scrap_quantity,
            "scrap",
            qc_department.id,
            order.target_tag_set_id,
        )
        _record_loss(
            session,
            production_item,
            order,
            batch,
            node["id"],
            payload.lost_quantity,
            "lost",
            qc_department.id,
            order.target_tag_set_id,
        )
        session.flush()
        _complete_batch(batch, payload, qc_worker)
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_batch(
            batch,
            rework_pending_quantity=payload.rework_quantity,
            track_rework=order.work_order_type == "tag",
        )


def _inspection_total(payload: QcInspection) -> int:
    return sum(
        (
            payload.qualified_quantity,
            payload.rework_quantity,
            payload.scrap_quantity,
            payload.lost_quantity,
        )
    )


def _record_loss(
    session,
    production_item,
    order,
    batch,
    flow_node_id,
    quantity,
    movement_type,
    qc_department_id,
    source_tag_set_id,
) -> None:
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type=movement_type,
        source_flow_node_id=flow_node_id,
        target_flow_node_id=None,
        source_tag_set_id=source_tag_set_id,
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
