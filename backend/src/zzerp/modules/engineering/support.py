from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import BomItemPayload, ProcessFlowPayload
from zzerp.modules.engineering.flow import validate_process_flow
from zzerp.modules.engineering.rules import BomItemCommand


def empty_process_flow() -> dict:
    return {"schema_version": 8, "nodes": [], "edges": []}


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


def validated_flow(flow: ProcessFlowPayload) -> dict:
    return validate_process_flow(flow).model_dump(exclude_none=True)


def raise_integrity_error(exc: IntegrityError) -> None:
    diagnostic = getattr(getattr(exc, "orig", None), "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", "") or ""
    table_name = getattr(diagnostic, "table_name", "") or ""
    column_name = getattr(diagnostic, "column_name", "") or ""
    if constraint_name == "uq_product_appearance_name":
        raise DomainError(
            "appearance_name_conflict",
            "该产品已存在同名外观",
            status_code=409,
            path="appearance_name",
        ) from exc
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
    if constraint_name == "uq_product_process_flow_appearance":
        raise DomainError(
            "process_flow_appearance_conflict",
            "当前产品外观已存在工序流程记录，请刷新后重试",
            status_code=409,
            path="process_flow",
        ) from exc
    if constraint_name == "fk_product_process_flow_appearance":
        raise DomainError(
            "process_flow_appearance_missing",
            "当前产品外观不存在，无法保存工序流程",
            status_code=409,
            path="appearance_id",
        ) from exc
    if table_name == "product_process_flow" and column_name == "draft_flow_json":
        raise DomainError(
            "process_flow_draft_column_invalid",
            "数据库字段 draft_flow_json 不允许清空，请使用最新 zzerp.sql 重建数据库",
            status_code=409,
            path="process_flow",
        ) from exc
    if table_name == "product_process_flow":
        conflict = constraint_name or column_name or "未知约束"
        raise DomainError(
            "process_flow_storage_conflict",
            f"工序流程保存违反数据库约束：{conflict}",
            status_code=409,
            path="process_flow",
        ) from exc
    conflict = constraint_name or column_name or "未知约束"
    location = f"{table_name}.{conflict}" if table_name else conflict
    raise DomainError(
        "data_conflict",
        f"数据违反数据库约束：{location}",
        status_code=409,
    ) from exc


def raise_stale_data_error(exc: StaleDataError) -> None:
    raise DomainError(
        "product_revision_conflict",
        "产品资料已被其他用户更新，请重新加载后再保存",
        status_code=409,
        path="expected_revision",
    ) from exc
