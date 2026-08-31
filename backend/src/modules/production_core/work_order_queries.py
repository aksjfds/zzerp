from sqlalchemy import exists, func, or_, select

from database import SessionLocal
from domain.production_types import STANDARD_EXECUTION_WORK_ORDER_TYPES
from modules.engineering.model_api import Product, ProductBom, ProductRouteTask
from modules.production_core.persistence import (
    ProductionItem,
    ProductionOperationUndo,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.work_order_presenters import (
    WorkOrderPresenterContext,
    build_work_order_presenter_context,
    item_display,
    serialize_batch,
    work_order_context,
)
from modules.production_core.flow_api import qc_qualified_destinations


def list_qc_batches(
    page: int,
    page_size: int,
    production_item_id: int | None = None,
    history: bool = False,
    keyword: str | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        statement = select(WorkOrderBatch).join(
            WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id
        ).where(
            WorkOrder.work_order_type.in_(list(STANDARD_EXECUTION_WORK_ORDER_TYPES))
        )
        destination_pending = (
            (WorkOrderBatch.recorded_at.is_not(None))
            & (WorkOrderBatch.qualified_quantity > 0)
            & (WorkOrderBatch.destination_decided_at.is_(None))
        )
        if history:
            statement = statement.where(
                WorkOrderBatch.recorded_at.is_not(None),
                ~destination_pending,
            )
        else:
            statement = statement.where(
                (WorkOrderBatch.recorded_at.is_(None)) | destination_pending
            )
        if production_item_id is not None:
            statement = statement.where(_related_to_production_item(production_item_id))
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
        total = session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0
        batches = list(session.scalars(
            statement
            .order_by(WorkOrderBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        order_ids = {batch.work_order_id for batch in batches}
        orders = {
            order.id: order
            for order in session.scalars(
                select(WorkOrder).where(WorkOrder.id.in_(order_ids))
            )
        } if order_ids else {}
        context = _load_order_relations(session, list(orders.values()))
        visible: list[dict] = []
        for batch in batches:
            order = orders.get(batch.work_order_id)
            if order is None:
                continue
            is_active = batch.recorded_at is None or (
                (batch.qualified_quantity or 0) > 0
                and batch.destination_decided_at is None
            )
            if (history and not is_active) or (not history and is_active):
                item = _serialize_pending_batch(session, batch, context)
                visible.append(item)
        return visible, total


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


def _load_order_relations(
    session,
    orders: list[WorkOrder],
) -> WorkOrderPresenterContext:
    order_ids = [order.id for order in orders]
    batch_cache: dict[int, list[WorkOrderBatch]] = {}
    material_cache: dict[int, list[int]] = {}
    undo_cache: dict[int, ProductionOperationUndo] = {}
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
        for operation in session.scalars(
            select(ProductionOperationUndo)
            .where(
                ProductionOperationUndo.work_order_id.in_(order_ids),
                ProductionOperationUndo.status == "applied",
            )
            .order_by(
                ProductionOperationUndo.work_order_id,
                ProductionOperationUndo.id.desc(),
            )
        ):
            undo_cache.setdefault(operation.work_order_id, operation)
    return build_work_order_presenter_context(
        session,
        orders,
        batches=batch_cache,
        material_item_ids=material_cache,
        undo_operations=undo_cache,
    )


def _serialize_pending_batch(
    session,
    batch: WorkOrderBatch,
    context: WorkOrderPresenterContext,
) -> dict:
    order = session.get(WorkOrder, batch.work_order_id)
    customer_order, _, production_item, flow_context = work_order_context(
        session,
        order,
        context,
    )
    part_no, part_name = item_display(session, production_item, context.display)
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
            "allowed_destinations": list(
                qc_qualified_destinations(
                    flow_context.flow,
                    flow_context.nodes,
                    order.flow_node_id,
                )
            )
            if (
                batch.recorded_at is not None
                and batch.qualified_quantity
                and batch.destination_decided_at is None
            )
            else [],
        }
    )
    return data
