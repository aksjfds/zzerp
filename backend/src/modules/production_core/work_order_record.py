from __future__ import annotations

from domain.time import business_iso
from modules.production_core.work_order_progress import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
)
from modules.production_core.work_order_support import (
    work_order_submission_capabilities,
)


def build_work_order_record(
    *,
    node,
    flow,
    nodes,
    procedure,
    workshop,
    order,
    batches,
):
    output_unit_quantity = (
        max(int(node.get("output_pcs") or 1), 1)
        if node.get("type") == "assembly" else 1
    )
    work_order_progress = calculate_work_order_progress(order, batches)
    progress = (
        calculate_assembly_output_progress(
            order,
            batches,
            output_unit_quantity,
        )
        if node.get("type") == "assembly"
        else work_order_progress
    )
    submission_capabilities = work_order_submission_capabilities(
        order,
        flow,
        nodes,
    )
    return {
        "id": order.id,
        "work_order_no": order.work_order_no,
        "work_order_type": order.work_order_type,
        "is_temporary": order.is_temporary,
        "qc_available": submission_capabilities.qc_available,
        "direct_result_allowed": submission_capabilities.direct_result_allowed,
        "output_unit_quantity": output_unit_quantity,
        "procedure_name": (
            procedure.procedure_name
            if procedure else str(node.get("label") or "—")
        ),
        "workshop_name": (
            workshop.workshop_name
            if workshop else str(node.get("label") or "—")
        ),
        "worker_name": order.worker_name,
        "work_order_quantity": order.quantity,
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
    }, progress
