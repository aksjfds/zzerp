"""Transaction-aware creation API for quality-owned inspection batches."""

from modules.quality.persistence import WorkOrderBatch


def create_inspection_batch(
    session,
    *,
    work_order_id: int,
    submitted_quantity: int,
    source_flow_node_id: str,
    rework_source_batch_id: int | None = None,
) -> WorkOrderBatch:
    batch = WorkOrderBatch(
        work_order_id=work_order_id,
        submitted_quantity=submitted_quantity,
        source_flow_node_id=source_flow_node_id,
        rework_source_batch_id=rework_source_batch_id,
    )
    session.add(batch)
    session.flush()
    return batch


__all__ = ["create_inspection_batch"]
