"""Read models for business-owned supplier-processing tasks."""

from dataclasses import asdict

from database import SessionLocal
from domain.time import business_iso
from modules.errors import DomainError
from modules.planning.supplier_processing_api import (
    list_supplier_processing_tasks,
)
from modules.production_core.reference_api import (
    SupplierProcessingQcOrderReference,
    supplier_processing_qc_order_references,
)


def list_tasks(
    *,
    production_plan_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        tasks = list_supplier_processing_tasks(
            session,
            production_plan_id=production_plan_id,
        )
        data = [asdict(task) for task in tasks]
        return data, len(data)


def list_qc_tasks() -> tuple[list[dict], int]:
    with SessionLocal() as session:
        tasks = list_supplier_processing_tasks(session)
        tasks_by_order_id = {
            task.work_order_id: task
            for task in tasks
            if task.work_order_id is not None and task.work_order_status == "open"
        }
        order_references = supplier_processing_qc_order_references(
            session,
        )
        if set(tasks_by_order_id) != set(order_references):
            raise DomainError(
                "supplier_processing_qc_context_missing",
                "开放委外加工工单与生产计划任务不一致",
                status_code=409,
            )
        data = []
        for order in order_references.values():
            task = tasks_by_order_id[order.id]
            data.append(_serialize_qc_task(task, order))
        return data, len(data)


def _serialize_qc_task(task, order: SupplierProcessingQcOrderReference) -> dict:
    return {
        "production_plan_id": task.production_plan_id,
        "production_plan_item_id": task.production_plan_item_id,
        "production_item_id": task.production_item_id,
        "customer_order_item_id": task.customer_order_item_id,
        "product_id": task.product_id,
        "product_version": task.product_version,
        "product_bom_id": task.product_bom_id,
        "source_flow_node_id": task.source_flow_node_id,
        "supplier_flow_node_id": task.supplier_flow_node_id,
        "item_code": task.item_code,
        "item_name": task.item_name,
        "work_order_id": order.id,
        "work_order_no": order.work_order_no,
        "supplier_name": order.supplier_name,
        "supplier_process_name": order.supplier_process_name,
        "remark": order.remark,
        "task_quantity": order.quantity,
        "inspected_quantity": order.inspected_quantity,
        "qualified_quantity": order.qualified_quantity,
        "rework_quantity": order.rework_quantity,
        "scrap_quantity": order.scrap_quantity,
        "lost_quantity": order.lost_quantity,
        "remaining_qualified_quantity": order.remaining_qualified_quantity,
        "pending_destination_quantity": order.pending_destination_quantity,
        "released_quantity": order.released_quantity,
        "status": order.status,
        "created_at": business_iso(order.created_at),
        "batches": [
            {
                "id": batch.id,
                "work_order_id": batch.work_order_id,
                "submitted_quantity": batch.submitted_quantity,
                "source_flow_node_id": batch.source_flow_node_id,
                "rework_source_batch_id": None,
                "rework_pending_quantity": 0,
                "qualified_quantity": batch.qualified_quantity,
                "rework_quantity": batch.rework_quantity,
                "scrap_quantity": batch.scrap_quantity,
                "lost_quantity": batch.lost_quantity,
                "qc_worker_id": batch.qc_worker_id,
                "qc_worker_name": batch.qc_worker_name,
                "defect_reason": batch.defect_reason,
                "qualified_destination": batch.qualified_destination,
                "destination_decided_at": business_iso(
                    batch.destination_decided_at
                ),
                "destination_decided_by": batch.destination_decided_by,
                "recorded_at": business_iso(batch.recorded_at),
            }
            for batch in order.batches
        ],
    }


__all__ = ["list_qc_tasks", "list_tasks"]
