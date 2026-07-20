from models.organization import Procedure, ProcedureTagSet
from models.production import ProcedureTagStock, Repository, WorkOrder
from services.errors import DomainError
from services.procedure_tags import tag_set_tags
from services.work_order_command_support import InventorySource


def normalize_tag_names(tag_names: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_name in tag_names:
        name = (raw_name or "").strip()
        if not name or name in normalized:
            continue
        if len(name) > 200:
            raise DomainError("procedure_tag_name_too_long", "生产标记名称不能超过 200 个字符")
        normalized.append(name)
    if not normalized:
        raise DomainError("procedure_applied_tags_empty", "请至少输入一个新增标记")
    if len(normalized) > 20:
        raise DomainError("procedure_applied_tags_too_many", "一张工单最多新增 20 个标记")
    return normalized


def validate_tag_source(
    session,
    source: InventorySource,
    procedure: Procedure,
) -> int | None:
    if isinstance(source, Repository):
        return None
    tag_set = session.get(ProcedureTagSet, source.tag_set_id)
    if tag_set is None or tag_set.procedure_id != procedure.id:
        raise DomainError("procedure_tag_set_invalid", "来源标记组合不属于当前流程工艺")
    return tag_set.id


def validate_tag_order(
    session,
    order: WorkOrder,
    source: InventorySource,
    procedure: Procedure,
) -> None:
    source_tag_set_id = source.tag_set_id if isinstance(source, ProcedureTagStock) else None
    validate_tag_order_snapshot(session, order, procedure, source_tag_set_id)


def validate_tag_order_snapshot(
    session,
    order: WorkOrder,
    procedure: Procedure,
    source_tag_set_id: int | None,
) -> None:
    applied_set = session.get(ProcedureTagSet, order.applied_tag_set_id)
    target_set = session.get(ProcedureTagSet, order.target_tag_set_id)
    source_tag_ids = [tag.id for tag in tag_set_tags(session, source_tag_set_id)]
    applied_tag_ids = [tag.id for tag in tag_set_tags(session, order.applied_tag_set_id)]
    target_tag_ids = [tag.id for tag in tag_set_tags(session, order.target_tag_set_id)]
    expected_target_ids = sorted(set(source_tag_ids) | set(applied_tag_ids))
    if (
        procedure.procedure_type != "standard"
        or order.procedure_id != procedure.id
        or applied_set is None
        or applied_set.procedure_id != procedure.id
        or not applied_tag_ids
        or bool(set(applied_tag_ids) & set(source_tag_ids))
        or target_set is None
        or target_set.procedure_id != procedure.id
        or source_tag_set_id != order.source_tag_set_id
        or target_tag_ids != expected_target_ids
    ):
        raise DomainError("procedure_tag_context_invalid", "工单标记组合与当前库存不一致")
