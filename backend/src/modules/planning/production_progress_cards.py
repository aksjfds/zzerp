from __future__ import annotations

"""Pure production-progress card calculation and mapping."""

from domain.time import business_iso
from modules.production_core.operational_api import calculate_assembly_output_progress, calculate_work_order_progress

def build_progress_card(
    *,
    node,
    procedure,
    workshop,
    department,
    orders,
    batches_by_order,
    workers,
    task_quantity,
    arrived_quantity,
    sort_order,
) -> dict:
    order_rows = []
    processing_quantity = 0
    ready_for_qc_quantity = 0
    pending_qc_quantity = 0
    completed_quantity = 0
    rework_quantity = 0
    scrap_quantity = 0
    lost_quantity = 0
    output_unit_quantity = (
        max(int(node.get("output_pcs") or 1), 1)
        if node.get("type") == "assembly" else 1
    )
    for order in orders:
        batches = batches_by_order.get(order.id, [])
        progress = (
            calculate_assembly_output_progress(
                order,
                batches,
                output_unit_quantity,
            )
            if node.get("type") == "assembly"
            else calculate_work_order_progress(order, batches)
        )
        processing_quantity += progress.processing_quantity
        ready_for_qc_quantity += progress.ready_for_qc_quantity
        pending_qc_quantity += progress.pending_qc_quantity
        completed_quantity += progress.qualified_quantity
        rework_quantity += progress.rework_quantity
        scrap_quantity += progress.scrap_quantity
        lost_quantity += progress.lost_quantity
        worker = workers.get(order.worker_id)
        order_rows.append({
            "id": order.id,
            "work_order_no": order.work_order_no,
            "worker_name": worker.worker_name if worker else None,
            "quantity": order.quantity * output_unit_quantity,
            "processed_quantity": progress.processed_quantity,
            "submitted_quantity": progress.submitted_quantity,
            "pending_qc_quantity": progress.pending_qc_quantity,
            "completed_quantity": progress.qualified_quantity,
            "rework_quantity": progress.rework_quantity,
            "scrap_quantity": progress.scrap_quantity,
            "lost_quantity": progress.lost_quantity,
            "status": order.status,
            "created_at": business_iso(order.created_at),
            "closed_at": business_iso(order.closed_at),
        })
    status = calculate_card_status(
        task_quantity,
        arrived_quantity,
        processing_quantity,
        ready_for_qc_quantity,
        pending_qc_quantity,
        completed_quantity,
        rework_quantity,
        scrap_quantity,
        lost_quantity,
    )
    card_type = (
        "assembly" if node.get("type") == "assembly"
        else "purchase" if procedure and procedure.procedure_type == "purchase_receipt"
        else "process"
    )
    card_name = procedure.procedure_name if procedure else "尚未开工单"
    return {
        "card_key": f"{card_type}:{node['id']}:{procedure.id if procedure else 'empty'}",
        "card_type": card_type,
        "sort_order": sort_order,
        "flow_node_id": node["id"],
        "procedure_id": procedure.id if procedure else None,
        "card_name": card_name,
        "department_code": department.department_code,
        "department_name": department.department_name,
        "workshop_name": workshop.workshop_name if workshop else department.department_name,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", "装配"),
        "status": status,
        "task_quantity": task_quantity,
        "arrived_quantity": arrived_quantity,
        "processing_quantity": processing_quantity,
        "ready_for_qc_quantity": ready_for_qc_quantity,
        "pending_qc_quantity": pending_qc_quantity,
        "completed_quantity": completed_quantity,
        "rework_quantity": rework_quantity,
        "scrap_quantity": scrap_quantity,
        "lost_quantity": lost_quantity,
        "work_orders": order_rows,
    }

def calculate_card_status(
    task_quantity,
    arrived_quantity,
    processing_quantity,
    ready_for_qc_quantity,
    pending_qc_quantity,
    completed_quantity,
    rework_quantity,
    scrap_quantity,
    lost_quantity,
) -> str:
    if rework_quantity or scrap_quantity or lost_quantity:
        return "exception"
    if completed_quantity >= task_quantity and task_quantity > 0:
        return "completed"
    if ready_for_qc_quantity or pending_qc_quantity:
        return "pending_qc"
    if processing_quantity:
        return "processing"
    if arrived_quantity:
        return "ready"
    return "not_arrived"


__all__ = ["build_progress_card", "calculate_card_status"]
