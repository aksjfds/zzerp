"""Pure quantity rules shared by the QC application workflow and tests."""

from modules.errors import DomainError


def validate_inspection_result(
    *,
    submitted_quantity: int,
    qualified_quantity: int,
    rework_quantity: int,
    scrap_quantity: int,
    lost_quantity: int,
    defect_reason: str | None,
) -> None:
    total = sum(
        (
            qualified_quantity,
            rework_quantity,
            scrap_quantity,
            lost_quantity,
        )
    )
    if total != submitted_quantity:
        raise DomainError(
            "qc_quantity_mismatch",
            "质检结果合计必须等于送检数量",
        )
    if total - qualified_quantity > 0 and not (defect_reason or "").strip():
        raise DomainError(
            "defect_reason_required",
            "存在异常数量时必须填写不良原因",
        )


__all__ = ["validate_inspection_result"]
