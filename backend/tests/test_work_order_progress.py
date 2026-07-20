from datetime import UTC, datetime

from models.production import WorkOrder, WorkOrderBatch
from services.work_order_progress import calculate_work_order_progress


def _tag_order(quantity: int = 10, submitted: int = 0) -> WorkOrder:
    return WorkOrder(
        id=1,
        production_item_id=1,
        work_order_type="tag",
        flow_node_id="polish",
        work_order_name="粗光-粗1",
        quantity=quantity,
        completed_quantity=submitted,
        status="open",
    )


def _batch(
    batch_id: int,
    submitted: int,
    *,
    source_batch_id: int | None = None,
    qualified: int | None = None,
    rework: int | None = None,
    recorded: bool = False,
) -> WorkOrderBatch:
    return WorkOrderBatch(
        id=batch_id,
        work_order_id=1,
        submitted_quantity=submitted,
        source_flow_node_id="source",
        rework_source_batch_id=source_batch_id,
        qualified_quantity=qualified,
        rework_quantity=rework,
        recorded_at=datetime.now(UTC) if recorded else None,
    )


def test_pending_qc_does_not_remove_initial_processing_twice():
    order = _tag_order(submitted=4)
    batch = _batch(1, 4)

    progress = calculate_work_order_progress(order, [batch])

    assert progress.initial_processing_quantity == 6
    assert progress.processing_quantity == 6
    assert progress.pending_qc_quantity == 4
    assert not progress.can_complete


def test_rework_returns_to_processing_until_resubmitted():
    order = _tag_order(submitted=10)
    source = _batch(1, 10, qualified=7, rework=3, recorded=True)

    progress = calculate_work_order_progress(order, [source])

    assert progress.rework_pending_by_batch == {1: 3}
    assert progress.processing_quantity == 3
    assert not progress.can_complete


def test_partial_rework_resubmission_is_counted_once():
    order = _tag_order(submitted=10)
    source = _batch(1, 10, qualified=7, rework=3, recorded=True)
    resubmission = _batch(2, 2, source_batch_id=1)

    progress = calculate_work_order_progress(order, [source, resubmission])

    assert progress.rework_pending_by_batch == {1: 1}
    assert progress.processing_quantity == 1
    assert progress.pending_qc_quantity == 2


def test_completed_rework_chain_can_close():
    order = _tag_order(submitted=10)
    source = _batch(1, 10, qualified=7, rework=3, recorded=True)
    resubmission = _batch(
        2,
        3,
        source_batch_id=1,
        qualified=3,
        rework=0,
        recorded=True,
    )

    progress = calculate_work_order_progress(order, [source, resubmission])

    assert progress.rework_pending_quantity == 0
    assert progress.pending_qc_quantity == 0
    assert progress.can_complete
