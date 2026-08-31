from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select

from domain.production_types import (
    QC_DESTINATION_RELEASE,
    REWORK_TRACKED_WORK_ORDER_TYPES,
    WORK_ORDER_STATUS_CANCELLED,
    WORK_ORDER_STATUS_CLOSED,
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_SUPPLIER_PROCESSING,
)
from domain.time import utc_now
from modules.errors import DomainError
from modules.production_core.context_api import (
    InspectionBatchContext,
    WorkOrderContext,
)
from modules.production_core.persistence import WorkOrder, WorkOrderBatch


@dataclass(frozen=True)
class WorkOrderProgress:
    submitted_quantity: int
    processed_quantity: int
    ready_for_qc_quantity: int
    initial_processing_quantity: int
    processing_quantity: int
    pending_qc_quantity: int
    direct_quantity: int
    qualified_quantity: int
    rework_quantity: int
    rework_pending_quantity: int
    scrap_quantity: int
    lost_quantity: int
    rework_pending_by_batch: dict[int, int]

    @property
    def can_complete(self) -> bool:
        return self.pending_qc_quantity == 0 and self.rework_pending_quantity == 0


@dataclass(frozen=True)
class AssemblyOutputProgress:
    processed_quantity: int
    submitted_quantity: int
    ready_for_qc_quantity: int
    processing_quantity: int
    pending_qc_quantity: int
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int


@dataclass(frozen=True, slots=True)
class SupplierProcessingQcProgress:
    inspected_quantity: int
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    remaining_qualified_quantity: int
    pending_destination_quantity: int
    released_quantity: int


def calculate_supplier_processing_qc_progress(
    order: WorkOrderContext,
    batches: Iterable[InspectionBatchContext],
) -> SupplierProcessingQcProgress:
    if order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError(
            "supplier_processing_work_order_required",
            "当前工单不是委外加工工单",
            status_code=409,
        )
    inspected_quantity = 0
    qualified_quantity = 0
    rework_quantity = 0
    scrap_quantity = 0
    lost_quantity = 0
    pending_destination_quantity = 0
    released_quantity = 0
    for batch in batches:
        qualified, rework, scrap, lost = _supplier_processing_batch_quantities(
            order,
            batch,
        )
        inspected_quantity += batch.submitted_quantity
        qualified_quantity += qualified
        rework_quantity += rework
        scrap_quantity += scrap
        lost_quantity += lost
        if batch.qualified_destination == QC_DESTINATION_RELEASE:
            released_quantity += qualified
        else:
            pending_destination_quantity += qualified
    if qualified_quantity > order.quantity:
        raise DomainError(
            "supplier_processing_qualified_quantity_exceeded",
            "委外加工工单累计合格数量超过任务数量",
            status_code=409,
        )
    return SupplierProcessingQcProgress(
        inspected_quantity=inspected_quantity,
        qualified_quantity=qualified_quantity,
        rework_quantity=rework_quantity,
        scrap_quantity=scrap_quantity,
        lost_quantity=lost_quantity,
        remaining_qualified_quantity=order.quantity - qualified_quantity,
        pending_destination_quantity=pending_destination_quantity,
        released_quantity=released_quantity,
    )


def _supplier_processing_batch_quantities(
    order: WorkOrderContext,
    batch: InspectionBatchContext,
) -> tuple[int, int, int, int]:
    quantities = (
        batch.qualified_quantity,
        batch.rework_quantity,
        batch.scrap_quantity,
        batch.lost_quantity,
    )
    if (
        batch.work_order_id != order.id
        or batch.submitted_quantity <= 0
        or batch.recorded_at is None
        or any(quantity is None for quantity in quantities)
        or batch.rework_source_batch_id is not None
        or batch.source_flow_node_id != order.flow_node_id
        or batch.qualified_destination not in {None, QC_DESTINATION_RELEASE}
        or (
            batch.qualified_destination is None
            and batch.destination_decided_at is not None
        )
        or (
            batch.qualified_destination == QC_DESTINATION_RELEASE
            and batch.destination_decided_at is None
        )
    ):
        raise DomainError(
            "supplier_processing_qc_history_invalid",
            "委外加工工单存在不符合分次质检规则的批次",
            status_code=409,
        )
    qualified = batch.qualified_quantity or 0
    rework = batch.rework_quantity or 0
    scrap = batch.scrap_quantity or 0
    lost = batch.lost_quantity or 0
    if (
        any(quantity < 0 for quantity in (qualified, rework, scrap, lost))
        or qualified + rework + scrap + lost != batch.submitted_quantity
    ):
        raise DomainError(
            "supplier_processing_qc_history_invalid",
            "委外加工质检批次数量不守恒",
            status_code=409,
        )
    return qualified, rework, scrap, lost


def validate_supplier_processing_work_order_progress(
    order: WorkOrderContext,
    progress: SupplierProcessingQcProgress,
) -> None:
    released_quantity = progress.released_quantity
    if (
        order.processed_quantity != released_quantity
        or order.completed_quantity != released_quantity
        or released_quantity > order.quantity
        or (
            order.status == WORK_ORDER_STATUS_OPEN
            and released_quantity >= order.quantity
        )
        or (
            order.status == WORK_ORDER_STATUS_CLOSED
            and released_quantity != order.quantity
        )
        or (
            order.status == WORK_ORDER_STATUS_CANCELLED
            and released_quantity != 0
        )
    ):
        raise DomainError(
            "supplier_processing_progress_invalid",
            "委外加工工单放行进度与质检历史不一致",
            status_code=409,
        )


def order_remaining_quantity(order: WorkOrder) -> int:
    """Quantity that has not entered direct completion or an initial QC batch."""
    return max(order.quantity - order.completed_quantity, 0)


def order_has_submissions(order: WorkOrder) -> bool:
    return order.completed_quantity > 0 or order.processed_quantity > 0


def order_remaining_expression():
    """SQL expression matching order_remaining_quantity for valid work orders."""
    return WorkOrder.quantity - WorkOrder.completed_quantity


def rework_resubmitted_quantities(
    batches: Iterable[WorkOrderBatch],
) -> dict[int, int]:
    submitted_by_source: dict[int, int] = defaultdict(int)
    for batch in batches:
        if batch.rework_source_batch_id is not None:
            submitted_by_source[batch.rework_source_batch_id] += batch.submitted_quantity
    return dict(submitted_by_source)


def rework_pending_quantities(
    batches: Iterable[WorkOrderBatch],
) -> dict[int, int]:
    batch_list = list(batches)
    resubmitted = rework_resubmitted_quantities(batch_list)
    return {
        batch.id: max(
            (batch.rework_quantity or 0) - resubmitted.get(batch.id, 0),
            0,
        )
        for batch in batch_list
        if batch.recorded_at is not None
    }


def rework_pending_by_order(
    batches: Iterable[WorkOrderBatch],
) -> dict[int, int]:
    batch_list = list(batches)
    pending_by_batch = rework_pending_quantities(batch_list)
    result: dict[int, int] = defaultdict(int)
    for batch in batch_list:
        result[batch.work_order_id] += pending_by_batch.get(batch.id, 0)
    return dict(result)


def calculate_work_order_progress(
    order: WorkOrder,
    batches: Iterable[WorkOrderBatch],
) -> WorkOrderProgress:
    batch_list = list(batches)
    completed_batches = [batch for batch in batch_list if batch.recorded_at is not None]
    pending_batches = [batch for batch in batch_list if batch.recorded_at is None]
    destination_pending_quantity = sum(
        batch.qualified_quantity or 0
        for batch in completed_batches
        if batch.qualified_quantity and batch.destination_decided_at is None
    )
    initial_batches = [
        batch for batch in batch_list if batch.rework_source_batch_id is None
    ]
    track_rework = order.work_order_type in REWORK_TRACKED_WORK_ORDER_TYPES
    rework_pending_by_batch = (
        rework_pending_quantities(batch_list) if track_rework else {}
    )
    rework_pending = sum(rework_pending_by_batch.values())
    initial_processing = max(order.quantity - order.processed_quantity, 0)
    ready_for_qc = max(order.processed_quantity - order.completed_quantity, 0)
    direct_quantity = max(
        order.completed_quantity
        - sum(batch.submitted_quantity for batch in initial_batches),
        0,
    )
    return WorkOrderProgress(
        submitted_quantity=order.completed_quantity,
        processed_quantity=order.processed_quantity,
        ready_for_qc_quantity=ready_for_qc,
        initial_processing_quantity=initial_processing,
        processing_quantity=initial_processing + rework_pending,
        pending_qc_quantity=(
            sum(batch.submitted_quantity for batch in pending_batches)
            + destination_pending_quantity
        ),
        direct_quantity=direct_quantity,
        qualified_quantity=direct_quantity
        + sum(
            batch.qualified_quantity or 0
            for batch in completed_batches
            if batch.destination_decided_at is not None
        ),
        rework_quantity=sum(batch.rework_quantity or 0 for batch in completed_batches),
        rework_pending_quantity=rework_pending,
        scrap_quantity=sum(batch.scrap_quantity or 0 for batch in completed_batches),
        lost_quantity=sum(batch.lost_quantity or 0 for batch in completed_batches),
        rework_pending_by_batch=rework_pending_by_batch,
    )


def calculate_assembly_output_progress(
    order: WorkOrder,
    batches: Iterable[WorkOrderBatch],
    output_unit_quantity: int,
) -> AssemblyOutputProgress:
    """Return assembly progress consistently in assembly-output units."""
    unit_quantity = max(int(output_unit_quantity), 1)
    batch_list = list(batches)
    pending_batches = [batch for batch in batch_list if batch.recorded_at is None]
    completed_batches = [batch for batch in batch_list if batch.recorded_at is not None]
    destination_pending_quantity = sum(
        batch.qualified_quantity or 0
        for batch in completed_batches
        if batch.qualified_quantity and batch.destination_decided_at is None
    )
    initial_batches = [
        batch for batch in batch_list if batch.rework_source_batch_id is None
    ]
    initial_submitted_quantity = sum(
        batch.submitted_quantity for batch in initial_batches
    )
    rework_pending = sum(rework_pending_quantities(batch_list).values())
    direct_quantity = max(
        order.completed_quantity * unit_quantity - initial_submitted_quantity,
        0,
    )
    operated_quantity = max(
        order.processed_quantity,
        order.completed_quantity,
    )
    return AssemblyOutputProgress(
        processed_quantity=operated_quantity * unit_quantity,
        submitted_quantity=order.completed_quantity * unit_quantity,
        ready_for_qc_quantity=max(
            order.processed_quantity - order.completed_quantity,
            0,
        ) * unit_quantity,
        processing_quantity=(
            max(order.quantity - operated_quantity, 0) * unit_quantity
            + rework_pending
        ),
        pending_qc_quantity=(
            sum(batch.submitted_quantity for batch in pending_batches)
            + destination_pending_quantity
        ),
        qualified_quantity=direct_quantity + sum(
            batch.qualified_quantity or 0
            for batch in completed_batches
            if batch.destination_decided_at is not None
        ),
        rework_quantity=sum(
            batch.rework_quantity or 0 for batch in completed_batches
        ),
        scrap_quantity=sum(
            batch.scrap_quantity or 0 for batch in completed_batches
        ),
        lost_quantity=sum(
            batch.lost_quantity or 0 for batch in completed_batches
        ),
    )


def refresh_qc_work_order_closed(session, order: WorkOrder) -> bool:
    if (
        order.work_order_type not in REWORK_TRACKED_WORK_ORDER_TYPES
        or order.status != WORK_ORDER_STATUS_OPEN
    ):
        return False
    batches = list(session.scalars(
        select(WorkOrderBatch).where(WorkOrderBatch.work_order_id == order.id)
    ).all())
    progress = calculate_work_order_progress(order, batches)
    if can_close_production_work_order(order, progress):
        order.status = WORK_ORDER_STATUS_CLOSED
        order.closed_at = utc_now()
        return True
    return False


def can_close_production_work_order(
    order: WorkOrder,
    progress: WorkOrderProgress,
) -> bool:
    """Return whether standard or assembly execution has fully settled."""
    return (
        order.work_order_type in REWORK_TRACKED_WORK_ORDER_TYPES
        and order.status == "open"
        and order.completed_quantity == order.quantity
        and progress.can_complete
    )
