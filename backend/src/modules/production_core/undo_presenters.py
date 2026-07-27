"""Read helpers for undo metadata, independent from undo command handling."""

from modules.production_core.persistence import ProductionOperationUndo
from sqlalchemy import select


def serialize_undo_operation(
    operation: ProductionOperationUndo | None,
) -> dict | None:
    if operation is None:
        return None
    return {
        "id": operation.id,
        "work_order_batch_id": operation.work_order_batch_id,
        "operation_type": operation.operation_type,
        "operation_label": operation.operation_label,
        "actor_username": operation.actor_username,
        "created_at": (
            operation.created_at.isoformat() if operation.created_at else None
        ),
    }


def latest_undoable_operation(
    session,
    work_order_id: int,
) -> ProductionOperationUndo | None:
    return session.scalar(
        select(ProductionOperationUndo)
        .where(
            ProductionOperationUndo.work_order_id == work_order_id,
            ProductionOperationUndo.status == "applied",
        )
        .order_by(ProductionOperationUndo.id.desc())
        .limit(1)
    )


__all__ = ["latest_undoable_operation", "serialize_undo_operation"]
