from sqlalchemy import select

from models.organization import Department, Worker
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch, WorkOrderMaterial
from models.sales import CustomerOrder
from services.production_flow import load_production_flow


def qc_repository_id(session, order: WorkOrder, batch: WorkOrderBatch) -> int | None:
    department_id = session.scalar(
        select(Department.id).where(Department.department_code == "qc")
    )
    return session.scalar(
        select(Repository.id).where(
            Repository.production_item_id == order.production_item_id,
            Repository.flow_node_id == batch.flow_node_id,
            Repository.source_flow_node_id == order.flow_node_id,
            Repository.department_id == department_id,
        )
    )


def work_order_context(session, order: WorkOrder):
    production_item = session.get(ProductionItem, order.production_item_id)
    flow_context = load_production_flow(session, production_item)
    customer_order = session.get(CustomerOrder, flow_context.order_item.customer_order_id)
    return customer_order, flow_context.bom_item, production_item


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
            WorkOrder.procedure_id.is_(None),
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
            WorkOrder.procedure_id.is_(None),
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
    production_items.sort(key=lambda item: (production_item_sort_order(session, item, visited), item.id))
    names: list[str] = []
    for production_item in production_items:
        name = production_item_name(session, production_item, visited)
        base_name = name.removesuffix("装配体")
        if base_name and base_name not in names:
            names.append(base_name)
    if names:
        return f"{'-'.join(names)}装配体"
    flow_context = load_production_flow(session, session.get(ProductionItem, order.production_item_id))
    assembly_node = flow_context.nodes.get(order.flow_node_id, {})
    return assembly_node.get("output_name") or assembly_node.get("label") or "装配体"


def serialize_batch(batch: WorkOrderBatch) -> dict:
    return {
        "id": batch.id,
        "work_order_id": batch.work_order_id,
        "submitted_quantity": batch.submitted_quantity,
        "flow_node_id": batch.flow_node_id,
        "qualified_quantity": batch.qualified_quantity,
        "rework_quantity": batch.rework_quantity,
        "scrap_quantity": batch.scrap_quantity,
        "lost_quantity": batch.lost_quantity,
        "qc_worker_name": batch.qc_worker_name,
        "defect_reason": batch.defect_reason,
        "recorded_at": batch.recorded_at.isoformat(timespec="minutes") if batch.recorded_at else None,
    }


def serialize_work_order(session, order: WorkOrder) -> dict:
    customer_order, _, production_item = work_order_context(session, order)
    part_no, part_name = item_display(session, production_item)
    if order.procedure_id is None:
        part_name = assembly_output_name(session, order)
        part_no = part_name
    worker = session.get(Worker, order.worker_id) if order.worker_id else None
    batch_cache = session.info.get("work_order_batch_cache")
    batches = batch_cache.get(order.id, []) if batch_cache is not None else session.scalars(
        select(WorkOrderBatch)
        .where(WorkOrderBatch.work_order_id == order.id)
        .order_by(WorkOrderBatch.id)
    ).all()
    completed_batches = [item for item in batches if item.recorded_at is not None]
    pending_batches = [item for item in batches if item.recorded_at is None]
    return {
        "id": order.id,
        "work_order_no": order.work_order_no,
        "repository_id": order.repository_id,
        "production_item_id": order.production_item_id,
        "customer_order_no": customer_order.customer_order_no,
        "part_no": part_no,
        "part_name": part_name,
        "procedure_name": order.procedure_name,
        "worker_id": order.worker_id,
        "worker_name": worker.worker_name if worker else None,
        "quantity": order.quantity,
        "submitted_quantity": order.completed_quantity,
        "processing_quantity": max(order.quantity - order.completed_quantity, 0),
        "pending_qc_quantity": sum(item.submitted_quantity for item in pending_batches),
        "qualified_quantity": sum(item.qualified_quantity or 0 for item in completed_batches),
        "rework_quantity": sum(item.rework_quantity or 0 for item in completed_batches),
        "scrap_quantity": sum(item.scrap_quantity or 0 for item in completed_batches),
        "lost_quantity": sum(item.lost_quantity or 0 for item in completed_batches),
        "status": order.status,
        "created_at": order.created_at.isoformat(timespec="minutes"),
        "closed_at": order.closed_at.isoformat(timespec="minutes") if order.closed_at else None,
        "batches": [serialize_batch(item) for item in batches],
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
