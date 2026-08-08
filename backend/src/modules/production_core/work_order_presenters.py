from sqlalchemy import select

from domain.time import business_iso
from domain.production_types import (
    REWORK_TRACKED_WORK_ORDER_TYPES,
    WORK_ORDER_ASSEMBLY,
)
from modules.engineering.model_api import Product
from modules.assembly.model_api import WorkOrderMaterial
from modules.quality.model_api import WorkOrderBatch
from modules.production_core.persistence import ProductionItem, WorkOrder
from modules.production_core.undo_presenters import (
    latest_undoable_operation,
    serialize_undo_operation,
)
from modules.sales.model_api import CustomerOrder
from modules.production_core.flow import load_production_flow, process_qc_node
from modules.production_core.work_order_progress import calculate_work_order_progress
from modules.workforce.reference_api import get_worker_reference


def work_order_context(session, order: WorkOrder):
    production_item = session.get(ProductionItem, order.production_item_id)
    flow_context = load_production_flow(session, production_item)
    customer_order = session.get(CustomerOrder, flow_context.order_item.customer_order_id)
    return customer_order, flow_context.bom_item, production_item, flow_context


def item_display(session, production_item: ProductionItem) -> tuple[str, str]:
    return load_production_flow(session, production_item).item_name(production_item)


def production_item_name(session, production_item: ProductionItem, visited: set[int]) -> str:
    if production_item.id in visited:
        return item_display(session, production_item)[1]
    context = load_production_flow(session, production_item)
    if context.bom_item is not None:
        return context.bom_item.part_name
    source_order = session.scalar(
        select(WorkOrder)
        .where(
            WorkOrder.production_item_id == production_item.id,
            WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
        )
        .order_by(WorkOrder.id.desc())
        .limit(1)
    )
    if source_order is not None:
        return assembly_output_name(session, source_order, visited | {production_item.id})
    return context.item_name(production_item)[1]


def production_item_sort_order(
    session, production_item: ProductionItem, visited: set[int]
) -> int:
    if production_item.id in visited:
        return 2**31 - 1
    context = load_production_flow(session, production_item)
    if context.bom_item is not None:
        return context.bom_item.sort_order
    source_order = session.scalar(
        select(WorkOrder)
        .where(
            WorkOrder.production_item_id == production_item.id,
            WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY,
        )
        .order_by(WorkOrder.id.desc())
        .limit(1)
    )
    if source_order is None:
        return 2**31 - 1
    source_ids = session.scalars(
        select(WorkOrderMaterial.production_item_id).where(
            WorkOrderMaterial.work_order_id == source_order.id
        )
    ).all()
    orders = [
        production_item_sort_order(
            session, item, visited | {production_item.id}
        )
        for item_id in source_ids
        if (item := session.get(ProductionItem, item_id)) is not None
    ]
    return min(orders, default=2**31 - 1)


def assembly_output_name(
    session, order: WorkOrder, visited: set[int] | None = None
) -> str:
    visited = visited or set()
    material_item_ids = session.scalars(
        select(WorkOrderMaterial.production_item_id)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all()
    production_items = [
        item
        for item_id in material_item_ids
        if (item := session.get(ProductionItem, item_id)) is not None
    ]
    production_items.sort(
        key=lambda item: (
            production_item_sort_order(session, item, visited),
            item.id,
        )
    )
    names: list[str] = []
    for production_item in production_items:
        name = production_item_name(session, production_item, visited)
        base_name = name.removesuffix("装配体")
        if base_name and base_name not in names:
            names.append(base_name)
    if names:
        return f"{'-'.join(names)}装配体"
    flow_context = load_production_flow(
        session,
        session.get(ProductionItem, order.production_item_id),
    )
    assembly_node = flow_context.nodes.get(order.flow_node_id, {})
    return assembly_node.get("output_name") or assembly_node.get("label") or "装配体"


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
        "recorded_at": business_iso(batch.recorded_at),
    }


def serialize_work_order(session, order: WorkOrder) -> dict:
    customer_order, _, production_item, flow_context = work_order_context(session, order)
    product = session.get(Product, production_item.product_id)
    procedure_name = flow_context.nodes.get(order.flow_node_id, {}).get("label") or ""
    part_no, part_name = flow_context.item_name(production_item)
    if order.work_order_type == WORK_ORDER_ASSEMBLY:
        part_name = assembly_output_name(session, order)
        part_no = part_name
    worker = (
        get_worker_reference(session, order.worker_id)
        if order.worker_id else None
    )
    batch_cache = session.info.get("work_order_batch_cache")
    batches = batch_cache.get(order.id, []) if batch_cache is not None else session.scalars(
        select(WorkOrderBatch)
        .where(WorkOrderBatch.work_order_id == order.id)
        .order_by(WorkOrderBatch.id)
    ).all()
    progress = calculate_work_order_progress(order, batches)
    undo_cache = session.info.get("work_order_undo_cache")
    undo_operation = (
        undo_cache.get(order.id)
        if undo_cache is not None
        else latest_undoable_operation(session, order.id)
    )
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
    return {
        "id": order.id,
        "work_order_no": order.work_order_no,
        "repository_id": order.repository_id,
        "procedure_tag_stock_id": order.procedure_tag_stock_id,
        "production_item_id": order.production_item_id,
        "procedure_id": order.procedure_id,
        "flow_node_id": order.flow_node_id,
        "source_flow_node_id": order.source_flow_node_id,
        "applied_tag_set_id": order.applied_tag_set_id,
        "source_tag_set_id": order.source_tag_set_id,
        "target_tag_set_id": order.target_tag_set_id,
        "work_order_type": order.work_order_type,
        "qc_required": process_qc_node(
            flow_context.flow,
            flow_context.nodes,
            order.flow_node_id,
        ) is not None,
        "customer_order_no": customer_order.customer_order_no,
        "factory_code": product.factory_code if product else "",
        "product_name": product.product_name if product else "",
        "part_no": part_no,
        "part_name": part_name,
        "procedure_name": procedure_name,
        "work_order_name": order.work_order_name,
        "remark": order.remark or "",
        "worker_id": order.worker_id,
        "worker_name": worker.worker_name if worker else None,
        "quantity": order.quantity,
        "processed_quantity": progress.processed_quantity,
        "submitted_quantity": progress.submitted_quantity,
        "ready_for_qc_quantity": progress.ready_for_qc_quantity,
        "processing_quantity": progress.processing_quantity,
        "pending_qc_quantity": progress.pending_qc_quantity,
        "qualified_quantity": progress.qualified_quantity,
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
            session.info["work_order_material_cache"].get(order.id, [])
            if "work_order_material_cache" in session.info
            else session.scalars(
                select(WorkOrderMaterial.production_item_id).where(
                    WorkOrderMaterial.work_order_id == order.id
                )
            ).all()
        ),
    }
