from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from models.production import WorkOrder, WorkOrderBatch


@dataclass(frozen=True)
class WorkOrderProgress:
    submitted_quantity: int
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


def order_remaining_quantity(order: WorkOrder) -> int:
    """Quantity that has not entered direct completion or an initial QC batch."""
    return max(order.quantity - order.completed_quantity, 0)


def order_has_submissions(order: WorkOrder) -> bool:
    return order.completed_quantity > 0


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
    initial_batches = [
        batch for batch in batch_list if batch.rework_source_batch_id is None
    ]
    track_rework = order.work_order_type == "tag"
    rework_pending_by_batch = (
        rework_pending_quantities(batch_list) if track_rework else {}
    )
    rework_pending = sum(rework_pending_by_batch.values())
    initial_processing = order_remaining_quantity(order)
    direct_quantity = max(
        order.completed_quantity
        - sum(batch.submitted_quantity for batch in initial_batches),
        0,
    )
    return WorkOrderProgress(
        submitted_quantity=order.completed_quantity,
        initial_processing_quantity=initial_processing,
        processing_quantity=initial_processing + rework_pending,
        pending_qc_quantity=sum(batch.submitted_quantity for batch in pending_batches),
        direct_quantity=direct_quantity,
        qualified_quantity=direct_quantity
        + sum(batch.qualified_quantity or 0 for batch in completed_batches),
        rework_quantity=sum(batch.rework_quantity or 0 for batch in completed_batches),
        rework_pending_quantity=rework_pending,
        scrap_quantity=sum(batch.scrap_quantity or 0 for batch in completed_batches),
        lost_quantity=sum(batch.lost_quantity or 0 for batch in completed_batches),
        rework_pending_by_batch=rework_pending_by_batch,
    )
