"""Pure current-material-state rows for the department task list."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from modules.production_core.model_api import WorkOrder, WorkOrderBatch
from modules.production_core.operational_api import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
)


TaskProcessingStatus = Literal[
    "not_started",
    "processing",
    "submitted_qc",
    "rework",
    "completed",
    "exception",
    "department_completed",
]
TaskStatusAction = Literal[
    "create_work_order",
    "view_work_orders",
    "none",
]
TaskCreationMode = Literal["repository", "assembly_initial"]

STATUS_ORDER: tuple[TaskProcessingStatus, ...] = (
    "not_started",
    "processing",
    "submitted_qc",
    "rework",
    "completed",
    "exception",
    "department_completed",
)


@dataclass(frozen=True, slots=True)
class TaskAvailableSource:
    repository_id: int | None
    completed_work_order_name: str | None
    creation_mode: TaskCreationMode
    quantity: int


@dataclass(slots=True)
class _StatusRow:
    status: TaskProcessingStatus
    label: str
    action: TaskStatusAction
    procedure_names: set[str] = field(default_factory=set)
    repository_ids: set[int] = field(default_factory=set)
    work_order_quantities: dict[int, int] = field(default_factory=dict)
    batch_quantities: dict[int, int] = field(default_factory=dict)
    creation_mode: TaskCreationMode | None = None
    quantity: int = 0


def build_task_processing_statuses(
    work_orders: list[WorkOrder],
    batches_by_order: dict[int, list[WorkOrderBatch]],
    *,
    available_sources: list[TaskAvailableSource],
    task_quantity: int,
    completed_quantity: int,
    assembly_output_unit_quantity: int | None = None,
) -> list[dict]:
    """Build actionable rows from available material and open work orders."""
    rows: dict[
        tuple[TaskProcessingStatus, str, TaskCreationMode | None],
        _StatusRow,
    ] = {}
    for source in available_sources:
        procedure_name = source.completed_work_order_name
        status: TaskProcessingStatus = "completed" if procedure_name else "not_started"
        label = f"{procedure_name}完" if procedure_name else "未加工"
        key = (status, label, source.creation_mode)
        row = rows.setdefault(
            key,
            _StatusRow(
                status=status,
                label=label,
                action="create_work_order",
                creation_mode=source.creation_mode,
            ),
        )
        row.quantity += source.quantity
        if procedure_name:
            row.procedure_names.add(procedure_name)
        if source.repository_id is not None:
            row.repository_ids.add(source.repository_id)

    for order in work_orders:
        if order.status == "cancelled":
            continue
        batches = batches_by_order.get(order.id, [])
        base = calculate_work_order_progress(order, batches)
        progress = (
            calculate_assembly_output_progress(
                order,
                batches,
                assembly_output_unit_quantity,
            )
            if assembly_output_unit_quantity is not None
            else base
        )
        if order.status == "open":
            _add_work_order_state(
                rows,
                status="processing",
                label=f"{order.work_order_name}中",
                quantity=max(
                    progress.processing_quantity - base.rework_pending_quantity,
                    0,
                ),
                order=order,
            )
        submitted_batches = [
            batch
            for batch in batches
            if batch.recorded_at is None
            or (
                (batch.qualified_quantity or 0) > 0
                and batch.destination_decided_at is None
            )
        ]
        submitted_batch_quantities = {
            batch.id: (
                batch.submitted_quantity
                if batch.recorded_at is None
                else (batch.qualified_quantity or 0)
            )
            for batch in submitted_batches
        }
        _add_work_order_state(
            rows,
            status="submitted_qc",
            label=f"{order.work_order_name}已送检",
            quantity=sum(submitted_batch_quantities.values()),
            order=order,
            batch_quantities=submitted_batch_quantities,
        )
        rework_batch_quantities = {
            batch_id: quantity
            for batch_id, quantity in base.rework_pending_by_batch.items()
            if quantity > 0
        }
        _add_work_order_state(
            rows,
            status="rework",
            label=f"{order.work_order_name}返工中",
            quantity=sum(rework_batch_quantities.values()),
            order=order,
            batch_quantities=rework_batch_quantities,
        )
        exception_batches = [
            batch
            for batch in batches
            if batch.recorded_at is not None
            and (batch.scrap_quantity or 0) + (batch.lost_quantity or 0) > 0
        ]
        _add_work_order_state(
            rows,
            status="exception",
            label=f"{order.work_order_name}异常",
            quantity=sum(
                (batch.scrap_quantity or 0) + (batch.lost_quantity or 0)
                for batch in exception_batches
            ),
            order=order,
            batch_quantities={
                batch.id: (
                    (batch.scrap_quantity or 0) + (batch.lost_quantity or 0)
                )
                for batch in exception_batches
            },
        )

    if not rows:
        if task_quantity > 0 and completed_quantity >= task_quantity:
            return [{
                "status": "department_completed",
                "label": "本部门任务已完成",
                "action": "none",
                "quantity": completed_quantity,
                "procedure_names": [],
                "repository_ids": [],
                "related_work_orders": [],
                "related_batches": [],
                "creation_mode": None,
            }]
        return [{
            "status": "not_started",
            "label": "等待物料",
            "action": "none",
            "quantity": max(task_quantity - completed_quantity, 0),
            "procedure_names": [],
            "repository_ids": [],
            "related_work_orders": [],
            "related_batches": [],
            "creation_mode": None,
        }]

    order_index = {status: index for index, status in enumerate(STATUS_ORDER)}
    ordered_rows = sorted(
        rows.values(),
        key=lambda row: (order_index[row.status], row.label, row.creation_mode or ""),
    )
    return [
        {
            "status": row.status,
            "label": row.label,
            "action": row.action,
            "quantity": row.quantity,
            "procedure_names": sorted(row.procedure_names),
            "repository_ids": sorted(row.repository_ids),
            "related_work_orders": [
                {"work_order_id": work_order_id, "quantity": quantity}
                for work_order_id, quantity in sorted(
                    row.work_order_quantities.items(),
                    reverse=True,
                )
            ],
            "related_batches": [
                {"batch_id": batch_id, "quantity": quantity}
                for batch_id, quantity in sorted(
                    row.batch_quantities.items(),
                    reverse=True,
                )
            ],
            "creation_mode": row.creation_mode,
        }
        for row in ordered_rows
    ]


def _add_work_order_state(
    rows: dict[
        tuple[TaskProcessingStatus, str, TaskCreationMode | None],
        _StatusRow,
    ],
    *,
    status: TaskProcessingStatus,
    label: str,
    quantity: int,
    order: WorkOrder,
    batch_quantities: dict[int, int] | None = None,
) -> None:
    if quantity <= 0:
        return
    key = (status, label, None)
    row = rows.setdefault(
        key,
        _StatusRow(
            status=status,
            label=label,
            action="view_work_orders",
        ),
    )
    row.quantity += quantity
    row.procedure_names.add(order.work_order_name)
    row.work_order_quantities[order.id] = (
        row.work_order_quantities.get(order.id, 0) + quantity
    )
    for batch_id, batch_quantity in (batch_quantities or {}).items():
        row.batch_quantities[batch_id] = (
            row.batch_quantities.get(batch_id, 0) + batch_quantity
        )


__all__ = [
    "TaskAvailableSource",
    "TaskCreationMode",
    "TaskProcessingStatus",
    "TaskStatusAction",
    "build_task_processing_statuses",
]
