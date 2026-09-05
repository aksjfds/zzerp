from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from database import SessionLocal
from domain.time import utc_now
from domain.identity import can_access_department
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    ProductionOperationUndo,
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.sales.transaction_api import restore_order_state
from modules.errors import DomainError
from modules.production_core.undo_presenters import latest_applied_operation
from modules.production_core.work_order_presenters import serialize_work_order


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _inventory_row(row) -> dict:
    data = {
        "id": row.id,
        "production_item_id": row.production_item_id,
        "processing_state_id": row.processing_state_id,
        "flow_node_id": row.flow_node_id,
        "source_flow_node_id": row.source_flow_node_id,
        "department_id": row.department_id,
        "source_work_order_id": row.source_work_order_id,
        "quantity": row.quantity,
    }
    return data


def capture_operation_state(
    session,
    order: WorkOrder,
    item_ids: set[int] | None = None,
) -> dict:
    materials = list(session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all())
    affected_ids = set(item_ids or ())
    affected_ids.add(order.production_item_id)
    affected_ids.update(material.production_item_id for material in materials)
    repositories = list(session.scalars(
        select(Repository)
        .where(Repository.production_item_id.in_(affected_ids))
        .order_by(Repository.id)
    ).all())
    production_items = list(session.scalars(
        select(ProductionItem)
        .where(ProductionItem.id.in_(affected_ids))
        .order_by(ProductionItem.id)
    ).all())
    order_item = session.get(
        CustomerOrderItem,
        production_items[0].customer_order_item_id,
    ) if production_items else None
    customer_order = session.get(CustomerOrder, order_item.customer_order_id) if order_item else None
    batches = list(session.scalars(
        select(WorkOrderBatch)
        .where(WorkOrderBatch.work_order_id == order.id)
        .order_by(WorkOrderBatch.id)
    ).all())
    return {
        "affected_item_ids": sorted(affected_ids),
        "order": {
            "production_item_id": order.production_item_id,
            "repository_id": order.repository_id,
            "processed_quantity": order.processed_quantity,
            "completed_quantity": order.completed_quantity,
            "status": order.status,
            "closed_at": _iso(order.closed_at),
        },
        "materials": [
            {"id": item.id, "repository_id": item.repository_id}
            for item in materials
        ],
        "repositories": [_inventory_row(item) for item in repositories],
        "production_items": [item.id for item in production_items],
        "batch_ids": [batch.id for batch in batches],
        "batches": [
            {
                "id": batch.id,
                "submitted_quantity": batch.submitted_quantity,
                "rework_source_batch_id": batch.rework_source_batch_id,
                "qualified_quantity": batch.qualified_quantity,
                "rework_quantity": batch.rework_quantity,
                "scrap_quantity": batch.scrap_quantity,
                "lost_quantity": batch.lost_quantity,
                "qc_worker_id": batch.qc_worker_id,
                "qc_worker_name": batch.qc_worker_name,
                "defect_reason": batch.defect_reason,
                "qualified_destination": batch.qualified_destination,
                "destination_decided_at": _iso(batch.destination_decided_at),
                "destination_decided_by": batch.destination_decided_by,
                "recorded_at": _iso(batch.recorded_at),
            }
            for batch in batches
        ],
        "movement_ids": list(session.scalars(
            select(ProductionMovement.id)
            .where(ProductionMovement.production_item_id.in_(affected_ids))
            .order_by(ProductionMovement.id)
        ).all()),
        "customer_order": (
            {
                "id": customer_order.id,
                "status": customer_order.status,
                "revision": customer_order.revision,
            }
            if customer_order else None
        ),
    }


def record_undoable_operation(
    session,
    order: WorkOrder,
    before: dict,
    *,
    operation_type: str,
    operation_label: str,
    department_code: str,
    actor_username: str,
    work_order_batch_id: int | None = None,
) -> ProductionOperationUndo:
    affected_ids = set(before["affected_item_ids"])
    affected_ids.add(order.production_item_id)
    after = capture_operation_state(session, order, affected_ids)
    created_batches = sorted(set(after["batch_ids"]) - set(before["batch_ids"]))
    operation = ProductionOperationUndo(
        work_order_id=order.id,
        work_order_batch_id=(
            work_order_batch_id
            if work_order_batch_id is not None
            else created_batches[-1] if created_batches else None
        ),
        operation_type=operation_type,
        operation_label=operation_label,
        department_code=department_code,
        actor_username=actor_username,
        snapshot_json={"before": before, "after": after},
    )
    session.add(operation)
    session.flush()
    return operation


def undo_production_operation(
    operation_id: int,
    user_department: str | None,
    user_is_system: bool,
    username: str,
) -> dict:
    with SessionLocal.begin() as session:
        return undo_production_operation_in_session(
            session,
            operation_id,
            user_department,
            user_is_system,
            username,
        )


def undo_production_operation_in_session(
    session,
    operation_id: int,
    user_department: str | None,
    user_is_system: bool,
    username: str,
) -> dict:
    operation = session.get(
        ProductionOperationUndo,
        operation_id,
        with_for_update=True,
    )
    if operation is None:
        raise DomainError("production_operation_not_found", "可撤回操作不存在", status_code=404)
    if operation.status != "applied":
        raise DomainError("production_operation_already_reversed", "该操作已经撤回")
    if not can_access_department(
        user_department,
        user_is_system,
        operation.department_code,
    ):
        raise DomainError("department_access_denied", "无权撤回该部门的生产操作", status_code=403)
    latest = latest_applied_operation(session, operation.work_order_id)
    if latest is None or latest.id != operation.id:
        raise DomainError("production_operation_not_latest", "请先撤回该工单更晚的操作")
    before = operation.snapshot_json["before"]
    after = operation.snapshot_json["after"]
    order = session.get(WorkOrder, operation.work_order_id, with_for_update=True)
    if order is None:
        raise DomainError("work_order_not_found", "工单不存在", status_code=404)

    _lock_operation_batches(session, after)
    _lock_operation_state(session, after)
    affected_ids = set(after["affected_item_ids"])
    current = capture_operation_state(session, order, affected_ids)
    if current != after:
        raise DomainError(
            "production_operation_has_downstream_changes",
            "该操作之后已有 QC、库存或工单变化，不能撤回",
        )

    current_repository_ids = {item["id"] for item in after["repositories"]}
    dependent_order = session.scalar(
        select(WorkOrder.id).where(
            WorkOrder.id != order.id,
            WorkOrder.created_at > operation.created_at,
            (
                WorkOrder.repository_id.in_(current_repository_ids)
                if current_repository_ids else WorkOrder.id < 0
            ),
        ).limit(1)
    )
    if dependent_order is not None:
        raise DomainError(
            "production_operation_inventory_reserved",
            "该操作产生或使用的数量已被其他工单占用，不能撤回",
        )
    dependent_material = session.scalar(
        select(WorkOrderMaterial.id)
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
        .where(
            WorkOrderMaterial.work_order_id != order.id,
            WorkOrderMaterial.repository_id.in_(current_repository_ids),
            WorkOrder.created_at > operation.created_at,
        ).limit(1)
    ) if current_repository_ids else None
    if dependent_material is not None:
        raise DomainError(
            "production_operation_inventory_reserved",
            "该操作产生的数量已被装配工单占用，不能撤回",
        )

    session.scalar(
        select(func.set_config(
            "zzerp.undo_operation_id",
            str(operation.id),
            True,
        ))
    )
    _restore_state(session, order, before, after)
    operation.status = "reversed"
    operation.reversed_at = utc_now()
    operation.reversed_by = username
    session.flush()
    return serialize_work_order(session, order)


def _lock_operation_state(session, state: dict) -> None:
    item_ids = set(state["affected_item_ids"])
    repository_ids = {item["id"] for item in state["repositories"]}
    if repository_ids:
        list(session.scalars(
            select(Repository)
            .where(Repository.id.in_(repository_ids))
            .with_for_update()
        ).all())
    if item_ids:
        list(session.scalars(
            select(ProductionItem)
            .where(ProductionItem.id.in_(item_ids))
            .with_for_update()
        ).all())
    customer_state = state.get("customer_order")
    if customer_state:
        session.get(CustomerOrder, customer_state["id"], with_for_update=True)


def _lock_operation_batches(session, state: dict) -> None:
    batch_ids = set(state["batch_ids"])
    if batch_ids:
        list(session.scalars(
            select(WorkOrderBatch)
            .where(WorkOrderBatch.id.in_(batch_ids))
            .with_for_update()
        ).all())


def _restore_state(session, order: WorkOrder, before: dict, after: dict) -> None:
    created_movement_ids = set(after["movement_ids"]) - set(before["movement_ids"])
    created_batch_ids = set(after["batch_ids"]) - set(before["batch_ids"])
    for movement in session.scalars(
        select(ProductionMovement).where(ProductionMovement.id.in_(created_movement_ids))
    ).all():
        session.delete(movement)
    session.flush()
    for batch in session.scalars(
        select(WorkOrderBatch).where(WorkOrderBatch.id.in_(created_batch_ids))
    ).all():
        session.delete(batch)
    _restore_batch_states(session, before["batches"])
    session.flush()

    before_repository_ids = {item["id"] for item in before["repositories"]}
    if order.repository_id not in before_repository_ids:
        order.repository_id = None
    materials = {
        item.id: item for item in session.scalars(
            select(WorkOrderMaterial).where(WorkOrderMaterial.work_order_id == order.id)
        ).all()
    }
    for material in materials.values():
        if material.repository_id not in before_repository_ids:
            material.repository_id = None
    order.production_item_id = before["order"]["production_item_id"]
    session.flush()

    _restore_inventory_table(session, Repository, before["repositories"], after["repositories"])
    session.flush()

    order.repository_id = before["order"]["repository_id"]
    order.processed_quantity = before["order"]["processed_quantity"]
    order.completed_quantity = before["order"]["completed_quantity"]
    order.status = before["order"]["status"]
    order.closed_at = (
        datetime.fromisoformat(before["order"]["closed_at"])
        if before["order"]["closed_at"] else None
    )
    for state in before["materials"]:
        materials[state["id"]].repository_id = state["repository_id"]
    session.flush()

    created_item_ids = set(after["production_items"]) - set(before["production_items"])
    for item in session.scalars(
        select(ProductionItem).where(ProductionItem.id.in_(created_item_ids))
    ).all():
        session.delete(item)

    customer_state = before.get("customer_order")
    if customer_state:
        restore_order_state(
            session,
            customer_state["id"],
            status=customer_state["status"],
            revision=customer_state["revision"],
        )


def _restore_batch_states(session, states: list[dict]) -> None:
    if not states:
        return
    batch_ids = [state["id"] for state in states]
    batches = {
        batch.id: batch
        for batch in session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.id.in_(batch_ids))
        ).all()
    }
    for state in states:
        batch = batches.get(state["id"])
        if batch is None:
            raise DomainError(
                "production_operation_batch_missing",
                "撤回所需的质检批次不存在",
            )
        for field in (
            "submitted_quantity",
            "rework_source_batch_id",
            "qualified_quantity",
            "rework_quantity",
            "scrap_quantity",
            "lost_quantity",
            "qc_worker_id",
            "qc_worker_name",
            "defect_reason",
            "qualified_destination",
            "destination_decided_by",
        ):
            setattr(batch, field, state[field])
        for field in ("destination_decided_at", "recorded_at"):
            value = state[field]
            setattr(batch, field, datetime.fromisoformat(value) if value else None)


def _restore_inventory_table(session, model, before_rows: list[dict], after_rows: list[dict]) -> None:
    before_by_id = {item["id"]: item for item in before_rows}
    after_ids = {item["id"] for item in after_rows}
    current = {
        item.id: item for item in session.scalars(
            select(model).where(model.id.in_(after_ids | set(before_by_id)))
        ).all()
    }
    for row_id in after_ids - set(before_by_id):
        if row_id in current:
            session.delete(current[row_id])
    for row_id, state in before_by_id.items():
        row = current.get(row_id)
        values = {key: value for key, value in state.items() if key != "id"}
        if row is None:
            session.add(model(id=row_id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
