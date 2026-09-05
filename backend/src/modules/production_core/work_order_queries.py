from sqlalchemy import exists, func, or_, select

from database import SessionLocal
from domain.production_types import STANDARD_EXECUTION_WORK_ORDER_TYPES
from modules.engineering.model_api import Product, ProductBom, ProductRouteTask
from modules.errors import DomainError
from modules.organization.model_api import Procedure, Workshop
from modules.production_core.persistence import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.production_core.work_order_record import build_work_order_record
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.work_order_presenters import (
    WorkOrderPresenterContext,
    build_work_order_presenter_context,
    item_display,
    serialize_batch,
    serialize_work_order,
    work_order_context,
)
from modules.production_core.flow_api import qc_qualified_destinations, qc_release_target
from modules.production_core.work_order_progress import rework_pending_quantities


def list_qc_inspection_batches(
    page: int,
    page_size: int,
    history: bool = False,
    keyword: str | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        statement = select(
            WorkOrderBatch.id.label("batch_id"),
        ).select_from(WorkOrderBatch).join(
            WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id
        ).where(
            WorkOrder.work_order_type.in_(list(STANDARD_EXECUTION_WORK_ORDER_TYPES)),
            _qc_batch_view_condition(history),
        )
        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword:
            statement = (
                statement
                .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
                .join(
                    CustomerOrderItem,
                    CustomerOrderItem.id == ProductionItem.customer_order_item_id,
                )
                .join(
                    CustomerOrder,
                    CustomerOrder.id == CustomerOrderItem.customer_order_id,
                )
                .join(Product, Product.id == ProductionItem.product_id)
                .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
            )
            for token in normalized_keyword.split():
                pattern = f"%{token}%"
                statement = statement.where(or_(
                    WorkOrder.work_order_no.ilike(pattern),
                    WorkOrder.work_order_name.ilike(pattern),
                    CustomerOrder.customer_order_no.ilike(pattern),
                    ProductBom.part_no.ilike(pattern),
                    ProductBom.part_name.ilike(pattern),
                    Product.factory_code.ilike(pattern),
                    Product.product_name.ilike(pattern),
                    exists(select(ProductRouteTask.id).where(
                        ProductRouteTask.product_id == ProductionItem.product_id,
                        ProductRouteTask.product_version == ProductionItem.product_version,
                        ProductRouteTask.origin_flow_node_id
                        == ProductionItem.origin_flow_node_id,
                        or_(
                            ProductRouteTask.origin_item_code.ilike(pattern),
                            ProductRouteTask.origin_item_name.ilike(pattern),
                        ),
                    )),
                ))
        total = int(session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0)
        batch_ids = list(session.scalars(
            statement.order_by(WorkOrderBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        if not batch_ids:
            return [], total

        batches = list(session.scalars(
            select(WorkOrderBatch)
            .where(WorkOrderBatch.id.in_(batch_ids))
        ))
        order_ids = {batch.work_order_id for batch in batches}
        orders = {
            order.id: order
            for order in session.scalars(
                select(WorkOrder).where(WorkOrder.id.in_(order_ids))
            )
        } if order_ids else {}
        context = _load_order_relations(session, list(orders.values()))
        batches_by_id = {batch.id: batch for batch in batches}
        batch_metadata = {
            order_id: _qc_batch_metadata(context.batches.get(order_id, []))
            for order_id in order_ids
        }
        return [
            _serialize_qc_inspection_batch(
                session,
                orders[batches_by_id[batch_id].work_order_id],
                batches_by_id[batch_id],
                context,
                batch_metadata[batches_by_id[batch_id].work_order_id],
            )
            for batch_id in batch_ids
        ], total


def get_qc_work_order_detail(work_order_id: int) -> dict:
    with SessionLocal() as session:
        order = session.get(WorkOrder, work_order_id)
        if (
            order is None
            or order.work_order_type not in STANDARD_EXECUTION_WORK_ORDER_TYPES
        ):
            raise DomainError(
                "qc_work_order_not_found",
                "质检工单不存在",
                status_code=404,
            )
        context = _load_order_relations(session, [order])
        _, _, _, flow_context = work_order_context(session, order, context)
        node = flow_context.nodes.get(order.flow_node_id)
        if node is None:
            raise DomainError(
                "qc_work_order_node_missing",
                "质检工单流程节点不存在",
            )
        procedure = (
            session.get(Procedure, order.procedure_id)
            if order.procedure_id is not None else None
        )
        workshop = (
            session.get(Workshop, procedure.workshop_id)
            if procedure is not None else None
        )
        record, _progress = build_work_order_record(
            node=node,
            flow=flow_context.flow,
            nodes=flow_context.nodes,
            procedure=procedure,
            workshop=workshop,
            order=order,
            batches=context.batches.get(order.id, []),
        )
        record["work_order"] = serialize_work_order(session, order, context)
        return record


def _qc_batch_view_condition(history: bool):
    destination_pending = (
        (WorkOrderBatch.recorded_at.is_not(None))
        & (WorkOrderBatch.qualified_quantity > 0)
        & (WorkOrderBatch.destination_decided_at.is_(None))
    )
    if history:
        return (WorkOrderBatch.recorded_at.is_not(None)) & ~destination_pending
    return (WorkOrderBatch.recorded_at.is_(None)) | destination_pending


def _load_order_relations(
    session,
    orders: list[WorkOrder],
) -> WorkOrderPresenterContext:
    order_ids = [order.id for order in orders]
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
    return build_work_order_presenter_context(
        session,
        orders,
        batches=batch_cache,
        material_item_ids=material_cache,
        undo_operations={},
    )


def _qc_batch_metadata(
    batches: list[WorkOrderBatch],
) -> tuple[dict[int, int], dict[int, int]]:
    return (
        {batch.id: index for index, batch in enumerate(batches, start=1)},
        rework_pending_quantities(batches),
    )


def _serialize_qc_inspection_batch(
    session,
    order: WorkOrder,
    batch: WorkOrderBatch,
    context: WorkOrderPresenterContext,
    metadata: tuple[dict[int, int], dict[int, int]],
) -> dict:
    customer_order, _, production_item, flow_context = work_order_context(
        session,
        order,
        context,
    )
    part_no, part_name = item_display(session, production_item, context.display)
    batch_sequence, pending_rework = metadata
    data = serialize_batch(
        batch,
        rework_pending_quantity=pending_rework.get(batch.id, 0),
        track_rework=True,
    )
    can_decide_destination = (
        batch.recorded_at is not None
        and bool(batch.qualified_quantity)
        and batch.destination_decided_at is None
    )
    allowed_destinations = (
        list(qc_qualified_destinations(
            flow_context.flow,
            flow_context.nodes,
            order.flow_node_id,
        ))
        if can_decide_destination
        else []
    )
    release_target = (
        qc_release_target(
            flow_context.flow,
            flow_context.nodes,
            order.flow_node_id,
        )
        if "release" in allowed_destinations
        else None
    )
    data.update({
        "production_item_id": production_item.id,
        "customer_order_no": customer_order.customer_order_no,
        "part_no": part_no,
        "part_name": part_name,
        "work_order_id": order.id,
        "work_order_no": order.work_order_no,
        "work_order_name": order.work_order_name,
        "worker_name": order.worker_name,
        "batch_sequence": batch_sequence[batch.id],
        "rework_source_batch_sequence": batch_sequence.get(
            batch.rework_source_batch_id
        ),
        "can_undo_inspection": (
            batch.recorded_at is not None
            and batch.destination_decided_at is None
            and not any(
                child.rework_source_batch_id == batch.id
                for child in context.batches.get(order.id, [])
            )
        ),
        "allowed_destinations": allowed_destinations,
        "release_target_name": (
            str(
                release_target.get("label")
                or release_target.get("output_name")
                or release_target["id"]
            )
            if release_target is not None
            else None
        ),
    })
    return data
