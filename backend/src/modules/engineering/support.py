from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from domain.models import BomItemCommand
from schemas.engineering import BomItemPayload, ProcessFlowPayload
from modules.errors import DomainError


def empty_process_flow() -> dict:
    return {"schema_version": 3, "nodes": [], "edges": []}


def bom_commands(items: list[BomItemPayload]) -> list[BomItemCommand]:
    return [
        BomItemCommand(
            id=item.id,
            part_name=item.part_name,
            part_no=item.part_no,
            pcs=item.pcs,
            remark=item.remark,
        )
        for item in items
    ]


def validated_flow(flow: ProcessFlowPayload, bom_ids: set[int]) -> dict:
    from domain.process_flow import validate_process_flow

    return validate_process_flow(flow, bom_ids).model_dump(exclude_none=True)


def raise_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(getattr(exc, "orig", None), "diag", None)
    constraint_name = getattr(constraint, "constraint_name", "")
    if constraint_name == "uq_product_factory_code":
        raise DomainError(
            "factory_code_conflict", "本厂型号已存在", status_code=409, path="factory_code"
        ) from exc
    if "customer_name" in constraint_name:
        raise DomainError(
            "customer_name_conflict",
            "客户名称已存在，请选择已有客户后重试",
            status_code=409,
            path="customer_name",
        ) from exc
    if constraint_name == "uq_product_bom_part_no":
        raise DomainError(
            "bom_part_no_conflict",
            "同一产品内的 BOM 配件编号不能重复",
            status_code=409,
            path="bom_items",
        ) from exc
    raise DomainError("data_conflict", "数据违反唯一性或关联约束", status_code=409) from exc


def raise_stale_data_error(exc: StaleDataError) -> None:
    raise DomainError(
        "product_version_conflict",
        "产品资料已被其他用户更新，请重新加载后再保存",
        status_code=409,
        path="expected_revision",
    ) from exc
