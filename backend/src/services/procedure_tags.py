from sqlalchemy import select

from models.organization import (
    Procedure,
    ProcedureTag,
    ProcedureTagPrice,
    ProcedureTagSet,
    ProcedureTagSetMember,
    Workshop,
)
from models.production import ProcedureTagStock, ProductionItem, Repository, WorkOrder
from services.errors import DomainError


def serialize_tag(tag: ProcedureTag) -> dict:
    return {"id": tag.id, "procedure_id": tag.procedure_id, "tag_name": tag.tag_name}


def tag_suggestions(session, procedure_id: int) -> list[ProcedureTag]:
    return list(
        session.scalars(
            select(ProcedureTag)
            .where(ProcedureTag.procedure_id == procedure_id)
            .order_by(ProcedureTag.tag_name, ProcedureTag.id)
        ).all()
    )


def configured_tag_suggestions(
    session,
    production_item: ProductionItem,
    procedure_id: int,
) -> list[ProcedureTag]:
    key = (
        production_item.product_id,
        production_item.product_version,
        production_item.origin_flow_node_id,
        procedure_id,
    )
    cache = session.info.setdefault("configured_procedure_tags_cache", {})
    if key not in cache:
        cache[key] = list(session.scalars(
            select(ProcedureTag)
            .join(
                ProcedureTagPrice,
                ProcedureTagPrice.procedure_tag_id == ProcedureTag.id,
            )
            .where(
                ProcedureTagPrice.product_id == production_item.product_id,
                ProcedureTagPrice.product_version == production_item.product_version,
                ProcedureTagPrice.origin_flow_node_id
                == production_item.origin_flow_node_id,
                ProcedureTagPrice.procedure_id == procedure_id,
            )
            .order_by(ProcedureTag.tag_name, ProcedureTag.id)
        ).all())
    return cache[key]


def required_tag_ids(
    session,
    production_item: ProductionItem,
    procedure_id: int,
) -> set[int]:
    return {
        tag.id
        for tag in configured_tag_suggestions(
            session,
            production_item,
            procedure_id,
        )
    }


def is_final_tag_set(
    session,
    production_item: ProductionItem,
    procedure_id: int,
    tag_set_id: int | None,
) -> bool:
    required_ids = required_tag_ids(session, production_item, procedure_id)
    if not required_ids or tag_set_id is None:
        return False
    return {tag.id for tag in tag_set_tags(session, tag_set_id)} == required_ids


def get_or_create_tag(session, procedure: Procedure, tag_name: str) -> ProcedureTag:
    name = (tag_name or "").strip()
    if not name:
        raise DomainError("procedure_tag_name_required", "请输入生产标记名称")
    if len(name) > 200:
        raise DomainError("procedure_tag_name_too_long", "生产标记名称不能超过 200 个字符")
    session.refresh(procedure, with_for_update=True)
    tag = session.scalar(
        select(ProcedureTag)
        .where(
            ProcedureTag.procedure_id == procedure.id,
            ProcedureTag.tag_name == name,
        )
        .with_for_update()
    )
    if tag is None:
        tag = ProcedureTag(procedure_id=procedure.id, tag_name=name)
        session.add(tag)
        session.flush()
    return tag


def tag_set_tags(session, tag_set_id: int | None) -> list[ProcedureTag]:
    if tag_set_id is None:
        return []
    cache = session.info.setdefault("procedure_tag_set_tags_cache", {})
    if tag_set_id not in cache:
        cache[tag_set_id] = list(
            session.scalars(
                select(ProcedureTag)
                .join(
                    ProcedureTagSetMember,
                    ProcedureTagSetMember.tag_id == ProcedureTag.id,
                )
                .where(ProcedureTagSetMember.tag_set_id == tag_set_id)
                .order_by(ProcedureTag.id)
            ).all()
        )
    return cache[tag_set_id]


def serialize_tag_set(session, tag_set_id: int | None) -> dict:
    tags = tag_set_tags(session, tag_set_id)
    return {
        "tag_set_id": tag_set_id,
        "tag_ids": [tag.id for tag in tags],
        "tag_names": [tag.tag_name for tag in tags],
        "tag_set_name": " + ".join(tag.tag_name for tag in tags) or "未打标记",
    }


def get_or_create_tag_set(
    session,
    procedure: Procedure,
    tag_ids: list[int],
) -> ProcedureTagSet:
    normalized_ids = sorted(set(tag_ids))
    if not normalized_ids:
        raise DomainError("procedure_tag_set_empty", "标记组合不能为空")
    tags = list(
        session.scalars(
            select(ProcedureTag).where(ProcedureTag.id.in_(normalized_ids))
        ).all()
    )
    if len(tags) != len(normalized_ids) or any(
        tag.procedure_id != procedure.id for tag in tags
    ):
        raise DomainError("procedure_tag_set_invalid", "标记组合不属于当前工艺")
    tag_key = ",".join(str(tag_id) for tag_id in normalized_ids)
    session.refresh(procedure, with_for_update=True)
    tag_set = session.scalar(
        select(ProcedureTagSet)
        .where(
            ProcedureTagSet.procedure_id == procedure.id,
            ProcedureTagSet.tag_key == tag_key,
        )
        .with_for_update()
    )
    if tag_set is None:
        tag_set = ProcedureTagSet(procedure_id=procedure.id, tag_key=tag_key)
        session.add(tag_set)
        session.flush()
        session.add_all(
            ProcedureTagSetMember(tag_set_id=tag_set.id, tag_id=tag_id)
            for tag_id in normalized_ids
        )
        session.flush()
    return tag_set


def target_tag_set(
    session,
    procedure: Procedure,
    source_tag_set_id: int | None,
    applied_tags: list[ProcedureTag],
) -> ProcedureTagSet:
    source_tags = tag_set_tags(session, source_tag_set_id)
    source_tag_ids = {tag.id for tag in source_tags}
    applied_tag_ids = {tag.id for tag in applied_tags}
    if not applied_tag_ids:
        raise DomainError("procedure_applied_tags_empty", "请至少输入一个新增标记")
    if source_tag_ids & applied_tag_ids:
        raise DomainError("procedure_tag_already_applied", "来源组合已经包含本次新增标记")
    return get_or_create_tag_set(
        session,
        procedure,
        list(source_tag_ids | applied_tag_ids),
    )


def procedure_department_id(session, procedure: Procedure) -> int:
    workshop = session.get(Workshop, procedure.workshop_id)
    if workshop is None:
        raise DomainError("procedure_department_missing", "当前工艺没有有效部门")
    return workshop.department_id


def upsert_tag_stock(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    tag_set_id: int,
    department_id: int,
    quantity: int,
) -> ProcedureTagStock | None:
    if quantity <= 0:
        return None
    session.get(ProductionItem, production_item.id, with_for_update=True)
    stock = session.scalar(
        select(ProcedureTagStock)
        .where(
            ProcedureTagStock.production_item_id == production_item.id,
            ProcedureTagStock.flow_node_id == flow_node_id,
            ProcedureTagStock.source_flow_node_id == source_flow_node_id,
            ProcedureTagStock.tag_set_id == tag_set_id,
            ProcedureTagStock.department_id == department_id,
        )
        .with_for_update()
    )
    if stock is None:
        stock = ProcedureTagStock(
            production_item_id=production_item.id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            tag_set_id=tag_set_id,
            department_id=department_id,
            quantity=quantity,
        )
        session.add(stock)
    else:
        stock.quantity += quantity
    return stock


def upsert_repository(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    department_id: int,
    quantity: int,
) -> Repository | None:
    if quantity <= 0:
        return None
    session.get(ProductionItem, production_item.id, with_for_update=True)
    repository = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item.id,
            Repository.flow_node_id == flow_node_id,
            Repository.source_flow_node_id == source_flow_node_id,
            Repository.department_id == department_id,
        )
        .with_for_update()
    )
    if repository is None:
        repository = Repository(
            production_item_id=production_item.id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            department_id=department_id,
            quantity=quantity,
        )
        session.add(repository)
    else:
        repository.quantity += quantity
    return repository


def consume_tag_stock(session, stock: ProcedureTagStock, quantity: int) -> None:
    remaining = stock.quantity - quantity
    if remaining < 0:
        raise DomainError("tag_stock_quantity_insufficient", "当前标记组合数量不足")
    if remaining:
        stock.quantity = remaining
        return
    referencing_orders = session.scalars(
        select(WorkOrder)
        .where(WorkOrder.procedure_tag_stock_id == stock.id)
        .with_for_update()
    ).all()
    for order in referencing_orders:
        order.procedure_tag_stock_id = None
    session.flush()
    session.delete(stock)


def route_tag_output(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    procedure: Procedure,
    target_tag_set_id: int,
    quantity: int,
) -> ProcedureTagStock | None:
    department_id = procedure_department_id(session, procedure)
    stock = upsert_tag_stock(
        session,
        production_item=production_item,
        flow_node_id=flow_node_id,
        source_flow_node_id=source_flow_node_id,
        tag_set_id=target_tag_set_id,
        department_id=department_id,
        quantity=quantity,
    )
    session.flush()
    return stock


def restore_tag_source(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    procedure: Procedure,
    source_tag_set_id: int | None,
    quantity: int,
) -> int:
    department_id = procedure_department_id(session, procedure)
    if source_tag_set_id is None:
        upsert_repository(
            session,
            production_item=production_item,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            department_id=department_id,
            quantity=quantity,
        )
    else:
        tag_set = session.get(ProcedureTagSet, source_tag_set_id)
        if tag_set is None or tag_set.procedure_id != procedure.id:
            raise DomainError("procedure_tag_set_invalid", "返工来源标记组合无效")
        upsert_tag_stock(
            session,
            production_item=production_item,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            tag_set_id=tag_set.id,
            department_id=department_id,
            quantity=quantity,
        )
    return department_id
