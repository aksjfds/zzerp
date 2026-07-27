from sqlalchemy import exists, func, or_, select

from database import SessionLocal
from domain.production_types import (
    MOVEMENT_QC_DISPATCH,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_PURCHASE_RECEIPT,
    WORK_ORDER_TAG,
)
from modules.organization.model_api import Department, Procedure, Workshop
from modules.standard_execution.model_api import ProcedureTagSetMember
from modules.assembly.model_api import WorkOrderMaterial
from modules.quality.model_api import WorkOrderBatch
from modules.production_core.persistence import (
    ProductionMovement,
    ProductionOperationUndo,
    WorkOrder,
)
from modules.errors import DomainError
from modules.production_core.work_order_presenters import (
    item_display,
    serialize_batch,
    serialize_work_order,
    work_order_context,
)
from modules.quality.integration_api import qc_release_context


def list_department_work_orders(
    department_code: str,
    page: int,
    page_size: int,
    production_item_id: int | None = None,
    flow_node_id: str | None = None,
    source_flow_node_id: str | None = None,
    existing_tag_ids: list[int] | None = None,
    applying_tag_ids: list[int] | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = _department(session, department_code)
        statement = (
            select(WorkOrder)
            .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
            .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
            .order_by(WorkOrder.id.desc())
        )
        condition = (
            WorkOrder.work_order_type == WORK_ORDER_ASSEMBLY
            if department_code == "assembly"
            else (
                (WorkOrder.work_order_type.in_((
                    WORK_ORDER_TAG,
                    WORK_ORDER_PURCHASE_RECEIPT,
                )))
                & (Workshop.department_id == department.id)
            )
        )
        if production_item_id is not None:
            condition = condition & _related_to_production_item(production_item_id)
        if flow_node_id is not None:
            condition = condition & (WorkOrder.flow_node_id == flow_node_id)
        if source_flow_node_id is not None:
            condition = condition & (
                WorkOrder.source_flow_node_id == source_flow_node_id
            )
        for existing_tag_id in existing_tag_ids or []:
            condition = condition & exists(
                select(ProcedureTagSetMember.id).where(
                    ProcedureTagSetMember.tag_set_id == WorkOrder.source_tag_set_id,
                    ProcedureTagSetMember.tag_id == existing_tag_id,
                )
            )
        for applying_tag_id in applying_tag_ids or []:
            condition = condition & exists(
                select(ProcedureTagSetMember.id).where(
                    ProcedureTagSetMember.tag_set_id == WorkOrder.applied_tag_set_id,
                    ProcedureTagSetMember.tag_id == applying_tag_id,
                )
            )
        filtered = statement.where(condition)
        total = session.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        ) or 0
        orders = session.scalars(
            filtered.offset((page - 1) * page_size).limit(page_size)
        ).all()
        _cache_order_relations(session, [order.id for order in orders])
        return [serialize_work_order(session, item) for item in orders], total


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
        )
        if history:
            statement = statement.where(WorkOrderBatch.recorded_at.is_not(None))
        else:
            statement = statement.where(
                or_(
                    WorkOrderBatch.recorded_at.is_(None),
                    WorkOrderBatch.qualified_quantity > 0,
                )
            )
        if production_item_id is not None:
            statement = statement.where(_related_to_production_item(production_item_id))
        batches = list(session.scalars(statement.order_by(WorkOrderBatch.id.desc())))
        batch_ids = [batch.id for batch in batches]
        order_ids = {batch.work_order_id for batch in batches}
        orders = {
            order.id: order
            for order in session.scalars(
                select(WorkOrder).where(WorkOrder.id.in_(order_ids))
            )
        } if order_ids else {}
        dispatched_by_batch = {
            batch_id: int(quantity or 0)
            for batch_id, quantity in session.execute(
                select(
                    ProductionMovement.work_order_batch_id,
                    func.sum(ProductionMovement.quantity),
                )
                .where(
                    ProductionMovement.work_order_batch_id.in_(batch_ids),
                    ProductionMovement.movement_type == MOVEMENT_QC_DISPATCH,
                )
                .group_by(ProductionMovement.work_order_batch_id)
            )
        } if batch_ids else {}
        visible: list[dict] = []
        normalized_keyword = (keyword or "").strip().lower()
        for batch in batches:
            order = orders.get(batch.work_order_id)
            if order is None:
                continue
            release = qc_release_context(
                session,
                batch,
                order,
                dispatched_by_batch.get(batch.id, 0),
            )
            is_active = batch.recorded_at is None or (
                release is not None and release["dispatchable_quantity"] > 0
            )
            if (history and not is_active) or (not history and is_active):
                item = _serialize_pending_batch(session, batch, release)
                if not normalized_keyword or _matches_qc_keyword(
                    item,
                    normalized_keyword,
                ):
                    visible.append(item)
        total = len(visible)
        return visible[(page - 1) * page_size:page * page_size], total


def _matches_qc_keyword(item: dict, keyword: str) -> bool:
    searchable = " ".join(
        str(item.get(field) or "")
        for field in (
            "work_order_no",
            "customer_order_no",
            "part_no",
            "part_name",
            "work_order_name",
        )
    ).lower()
    return all(token in searchable for token in keyword.split())


def _department(session, department_code: str) -> Department:
    department = session.scalar(
        select(Department).where(Department.department_code == department_code)
    )
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    return department


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


def _cache_order_relations(session, order_ids: list[int]) -> None:
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
    session.info["work_order_batch_cache"] = batch_cache
    session.info["work_order_material_cache"] = material_cache
    session.info["work_order_undo_cache"] = undo_cache


def _serialize_pending_batch(session, batch: WorkOrderBatch, release=None) -> dict:
    order = session.get(WorkOrder, batch.work_order_id)
    customer_order, _, production_item, _ = work_order_context(session, order)
    part_no, part_name = item_display(session, production_item)
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
            "dispatchable_quantity": (
                release["dispatchable_quantity"] if release is not None else 0
            ),
            "target_node_label": (
                release["target"].get("label", "")
                if release is not None and release["target"] is not None
                else None
            ),
        }
    )
    return data
