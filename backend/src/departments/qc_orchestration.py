"""Application orchestration for QC inspection and execution routing."""

from database import SessionLocal
from domain.identity import can_access_department
from domain.production_types import (
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_PURCHASE_RECEIPT,
    WORK_ORDER_STANDARD,
)
import modules.assembly.qc_api as assembly_qc_routing
from modules.errors import DomainError
import modules.purchasing.qc_api as purchase_qc_routing
from modules.quality.command_api import complete_inspection, prepare_inspection
from modules.quality.routing_contract import QcRoutingStrategy
import modules.standard_execution.qc_api as standard_qc_routing
from modules.workforce.reference_api import get_worker_reference
from schemas.production import QcInspection


QC_ROUTING_STRATEGIES: dict[str, QcRoutingStrategy] = {
    WORK_ORDER_STANDARD: standard_qc_routing,
    WORK_ORDER_PURCHASE_RECEIPT: purchase_qc_routing,
    WORK_ORDER_ASSEMBLY: assembly_qc_routing,
}


def inspect_qc_batch(
    batch_id: int,
    payload: QcInspection,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError("qc_access_denied", "只有 QC 可以录入质检结果", status_code=403)
    with SessionLocal.begin() as session:
        prepared = prepare_inspection(
            session,
            batch_id,
            payload,
            get_worker_reference(session, payload.qc_worker_id),
        )
        try:
            routing = QC_ROUTING_STRATEGIES[prepared.order.work_order_type]
        except KeyError as exc:
            raise DomainError(
                "qc_work_order_type_invalid",
                "当前工单不支持送 QC",
            ) from exc
        return complete_inspection(prepared, payload, routing)


__all__ = ["inspect_qc_batch"]
