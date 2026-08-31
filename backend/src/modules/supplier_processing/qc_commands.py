"""QC application workflow for supplier-processing work orders."""

from database import SessionLocal
from domain.identity import can_access_department
from modules.errors import DomainError
from modules.quality.supplier_processing_api import (
    record_supplier_processing_inspection as record_inspection,
)
from modules.workforce.reference_api import get_worker_reference


def record_supplier_processing_inspection(
    *,
    work_order_id: int,
    qc_worker_id: int,
    qualified_quantity: int,
    rework_quantity: int,
    scrap_quantity: int,
    lost_quantity: int,
    defect_reason: str | None,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError(
            "qc_access_denied",
            "只有 QC 可以录入委外质检结果",
            status_code=403,
        )
    with SessionLocal.begin() as session:
        return record_inspection(
            session,
            work_order_id=work_order_id,
            qualified_quantity=qualified_quantity,
            rework_quantity=rework_quantity,
            scrap_quantity=scrap_quantity,
            lost_quantity=lost_quantity,
            defect_reason=defect_reason,
            qc_worker=get_worker_reference(session, qc_worker_id),
        )


__all__ = ["record_supplier_processing_inspection"]
