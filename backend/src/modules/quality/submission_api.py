"""QC submission rules delegating batch persistence to production_core."""

from domain.production_types import (
    QC_SUPPORTED_WORK_ORDER_TYPES,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_STATUS_OPEN,
)
from modules.errors import DomainError
from modules.production_core.qc_api import (
    create_qc_batch,
    load_qc_batch,
    load_qc_work_order,
    rework_submitted_quantity,
)


def create_inspection_batch(
    session,
    *,
    work_order_id: int,
    submitted_quantity: int,
    execution_flow_node_id: str,
    rework_source_batch_id: int | None = None,
    expected_submission_quantity: int | None = None,
):
    order = load_qc_work_order(session, work_order_id, for_update=True)
    if order is None:
        raise DomainError("work_order_not_found", "送检工单不存在", status_code=404)
    if order.work_order_type not in QC_SUPPORTED_WORK_ORDER_TYPES:
        raise DomainError("qc_work_order_type_invalid", "当前工单不支持送QC")
    if order.status != WORK_ORDER_STATUS_OPEN:
        raise DomainError("work_order_closed", "生产工单已经结单")
    if execution_flow_node_id != order.flow_node_id:
        raise DomainError("qc_execution_node_invalid", "送检节点与工单执行节点不一致")

    if rework_source_batch_id is None:
        expected_quantity = (
            expected_submission_quantity
            if order.work_order_type == WORK_ORDER_ASSEMBLY
            else order.quantity
        )
        if expected_quantity is None or submitted_quantity != expected_quantity:
            raise DomainError(
                "work_order_full_quantity_required",
                "工单必须一次提交全部数量送检",
            )
    else:
        source_batch = load_qc_batch(session, rework_source_batch_id, for_update=True)
        if (
            source_batch is None
            or source_batch.work_order_id != order.id
            or source_batch.recorded_at is None
            or source_batch.rework_quantity is None
        ):
            raise DomainError("qc_rework_source_invalid", "返工来源批次无效")
        submitted = rework_submitted_quantity(session, order.id, source_batch.id)
        remaining = source_batch.rework_quantity - submitted
        if remaining <= 0 or submitted_quantity != remaining:
            raise DomainError(
                "qc_rework_full_quantity_required",
                "返工送检必须一次提交全部待返工数量",
            )

    return create_qc_batch(
        session,
        work_order_id=work_order_id,
        submitted_quantity=submitted_quantity,
        source_flow_node_id=execution_flow_node_id,
        rework_source_batch_id=rework_source_batch_id,
    )


__all__ = ["create_inspection_batch"]
