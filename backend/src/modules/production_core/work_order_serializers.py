from __future__ import annotations

"""Response serialization for work orders and QC batches."""

from domain.production_types import (
    REWORK_TRACKED_WORK_ORDER_TYPES,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_SUPPLIER_PROCESSING,
)
from domain.time import business_iso
from modules.production_core.flow import process_qc_node
from modules.production_core.persistence import WorkOrder, WorkOrderBatch
from modules.production_core.production_item_presenters import assembly_output_name
from modules.production_core.undo_presenters import serialize_undo_operation
from modules.production_core.work_order_presenter_context import (
    WorkOrderPresenterContext,
    work_order_context,
)
from modules.production_core.work_order_progress import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
)


def serialize_batch(
    batch: WorkOrderBatch,
    rework_pending_quantity: int = 0,
    track_rework: bool = False,
) -> dict:
    return {
        "id": batch.id,
        "work_order_id": batch.work_order_id,
        "submitted_quantity": batch.submitted_quantity,
        "source_flow_node_id": batch.source_flow_node_id,
        "rework_source_batch_id": batch.rework_source_batch_id,
        "rework_pending_quantity": (
            rework_pending_quantity
            if track_rework else 0
        ),
        "qualified_quantity": batch.qualified_quantity,
        "rework_quantity": batch.rework_quantity,
        "scrap_quantity": batch.scrap_quantity,
        "lost_quantity": batch.lost_quantity,
        "qc_worker_id": batch.qc_worker_id,
        "qc_worker_name": batch.qc_worker_name,
        "defect_reason": batch.defect_reason,
        "qualified_destination": batch.qualified_destination,
        "destination_decided_at": business_iso(batch.destination_decided_at),
        "destination_decided_by": batch.destination_decided_by,
        "recorded_at": business_iso(batch.recorded_at),
    }


def map_work_order(
    session,
    order: WorkOrder,
    context: WorkOrderPresenterContext,
) -> dict:
    customer_order, _, production_item, flow_context = work_order_context(
        session,
        order,
        context,
    )
    product = context.products.get(production_item.product_id)
    procedure = (
        context.procedures.get(order.procedure_id)
        if order.procedure_id is not None
        else None
    )
    if order.work_order_type == WORK_ORDER_SUPPLIER_PROCESSING:
        procedure_name = order.supplier_process_name
    else:
        procedure_name = procedure.procedure_name if procedure else order.work_order_name
    part_no, part_name = flow_context.item_name(production_item)
    if order.work_order_type == WORK_ORDER_ASSEMBLY:
        part_name = assembly_output_name(
            session,
            order,
            context=context.display,
        )
        part_no = part_name
    batches = context.batches.get(order.id, [])
    progress = calculate_work_order_progress(order, batches)
    output_unit_quantity = (
        int(flow_context.nodes.get(order.flow_node_id, {}).get("output_pcs", 1))
        if order.work_order_type == WORK_ORDER_ASSEMBLY
        else 1
    )
    assembly_output_progress = (
        calculate_assembly_output_progress(
            order,
            batches,
            output_unit_quantity,
        )
        if order.work_order_type == WORK_ORDER_ASSEMBLY
        else None
    )
    qualified_output_quantity = (
        assembly_output_progress.qualified_quantity
        if assembly_output_progress is not None
        else progress.qualified_quantity
    )
    undo_operation = context.undo_operations.get(order.id)
    if undo_operation is not None and undo_operation.work_order_batch_id is not None:
        operation_batch = next(
            (
                batch for batch in batches
                if batch.id == undo_operation.work_order_batch_id
            ),
            None,
        )
        if operation_batch is None or operation_batch.recorded_at is not None:
            undo_operation = None
    configured_qc = process_qc_node(
        flow_context.flow,
        flow_context.nodes,
        order.flow_node_id,
    ) is not None
    standard_execution = order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING
    qc_available = configured_qc and standard_execution
    direct_result_allowed = standard_execution
    return {
        "id": order.id,
        "work_order_no": order.work_order_no,
        "repository_id": order.repository_id,
        "production_item_id": order.production_item_id,
        "procedure_id": order.procedure_id,
        "flow_node_id": order.flow_node_id,
        "source_flow_node_id": order.source_flow_node_id,
        "work_order_type": order.work_order_type,
        "is_temporary": order.is_temporary,
        "supplier_name": order.supplier_name,
        "supplier_process_name": order.supplier_process_name,
        "qc_available": qc_available,
        "direct_result_allowed": direct_result_allowed,
        "customer_order_no": customer_order.customer_order_no,
        "factory_code": product.factory_code if product else "",
        "product_name": product.product_name if product else "",
        "part_no": part_no,
        "part_name": part_name,
        "procedure_name": procedure_name,
        "work_order_name": order.work_order_name,
        "created_by": order.created_by,
        "remark": order.remark or "",
        "worker_id": order.worker_id,
        "worker_name": order.worker_name,
        "quantity": order.quantity,
        "output_unit_quantity": output_unit_quantity,
        "output_quantity": order.quantity * output_unit_quantity,
        "processed_quantity": progress.processed_quantity,
        "submitted_quantity": progress.submitted_quantity,
        "ready_for_qc_quantity": progress.ready_for_qc_quantity,
        "processing_quantity": progress.processing_quantity,
        "processing_output_quantity": (
            assembly_output_progress.processing_quantity
            if assembly_output_progress is not None
            else progress.processing_quantity
        ),
        "ready_output_quantity": (
            assembly_output_progress.ready_for_qc_quantity
            if assembly_output_progress is not None
            else progress.ready_for_qc_quantity
        ),
        "pending_qc_quantity": progress.pending_qc_quantity,
        "qualified_quantity": progress.qualified_quantity,
        "qualified_output_quantity": qualified_output_quantity,
        "rework_quantity": progress.rework_quantity,
        "scrap_quantity": progress.scrap_quantity,
        "lost_quantity": progress.lost_quantity,
        "status": order.status,
        "created_at": business_iso(order.created_at),
        "closed_at": business_iso(order.closed_at),
        "batches": [
            serialize_batch(
                item,
                rework_pending_quantity=progress.rework_pending_by_batch.get(
                    item.id,
                    0,
                ),
                track_rework=order.work_order_type in REWORK_TRACKED_WORK_ORDER_TYPES,
            )
            for item in batches
        ],
        "undo_operation": serialize_undo_operation(undo_operation),
        "input_production_item_ids": (
            context.display.material_item_ids.get(order.id, [])
        ),
    }


__all__ = ["map_work_order", "serialize_batch"]
