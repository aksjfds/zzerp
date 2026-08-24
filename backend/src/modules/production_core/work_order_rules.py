"""Business invariants shared by all work-order record factories."""

from domain.production_types import (
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_PURCHASE_RECEIPT,
    WORK_ORDER_STANDARD,
)
from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext


def validate_work_order_procedure(
    procedure: ProcedureContext,
    work_order_type: str,
) -> None:
    expected = {
        WORK_ORDER_STANDARD: ("standard", "single"),
        WORK_ORDER_PURCHASE_RECEIPT: ("purchase_receipt", "single"),
        WORK_ORDER_ASSEMBLY: ("standard", "multiple"),
    }.get(work_order_type)
    if expected is None:
        raise DomainError("work_order_type_invalid", "工单类型无效")
    if (procedure.procedure_type, procedure.input_mode) != expected:
        raise DomainError(
            "work_order_procedure_invalid",
            "所选工艺不适用于当前工单类型",
        )


__all__ = ["validate_work_order_procedure"]
