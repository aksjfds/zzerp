from sqlalchemy import select

from models.organization import Procedure, ProcedureSubstep, Workshop
from models.production import (
    ProcedureStageStock,
    ProductionItem,
    Repository,
    WorkOrder,
)
from services.errors import DomainError


def serialize_substep(substep: ProcedureSubstep) -> dict:
    return {
        "id": substep.id,
        "procedure_id": substep.procedure_id,
        "substep_name": substep.substep_name,
    }


def substep_suggestions(session, procedure_id: int) -> list[ProcedureSubstep]:
    return list(
        session.scalars(
            select(ProcedureSubstep)
            .where(ProcedureSubstep.procedure_id == procedure_id)
            .order_by(ProcedureSubstep.substep_name, ProcedureSubstep.id)
        ).all()
    )


def get_or_create_substep(
    session,
    procedure: Procedure,
    substep_name: str,
) -> ProcedureSubstep:
    name = (substep_name or "").strip()
    if not name:
        raise DomainError("procedure_substep_name_required", "请输入细分工序名称")
    if len(name) > 200:
        raise DomainError("procedure_substep_name_too_long", "细分工序名称不能超过 200 个字符")

    # Locking the procedure serializes creation of a new reusable name and
    # prevents duplicate rows when two work orders introduce the same name.
    session.refresh(procedure, with_for_update=True)
    substep = session.scalar(
        select(ProcedureSubstep)
        .where(
            ProcedureSubstep.procedure_id == procedure.id,
            ProcedureSubstep.substep_name == name,
        )
        .with_for_update()
    )
    if substep is None:
        substep = ProcedureSubstep(
            procedure_id=procedure.id,
            substep_name=name,
        )
        session.add(substep)
        session.flush()
    return substep


def current_stage_name(
    session,
    procedure: Procedure,
    completed_substep_id: int | None,
) -> str:
    if completed_substep_id is None:
        return f"待{procedure.procedure_name}"
    substep = session.get(ProcedureSubstep, completed_substep_id)
    if substep is None or substep.procedure_id != procedure.id:
        return "未知细分工序"
    return substep.substep_name


def procedure_department_id(session, procedure: Procedure) -> int:
    workshop = session.get(Workshop, procedure.workshop_id)
    if workshop is None:
        raise DomainError("procedure_department_missing", "当前细分工序没有有效部门")
    return workshop.department_id


def upsert_stage_stock(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    completed_substep_id: int,
    department_id: int,
    quantity: int,
) -> ProcedureStageStock | None:
    if quantity <= 0:
        return None
    session.get(ProductionItem, production_item.id, with_for_update=True)
    stock = session.scalar(
        select(ProcedureStageStock)
        .where(
            ProcedureStageStock.production_item_id == production_item.id,
            ProcedureStageStock.flow_node_id == flow_node_id,
            ProcedureStageStock.source_flow_node_id == source_flow_node_id,
            ProcedureStageStock.completed_substep_id == completed_substep_id,
            ProcedureStageStock.department_id == department_id,
        )
        .with_for_update()
    )
    if stock is None:
        stock = ProcedureStageStock(
            production_item_id=production_item.id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            completed_substep_id=completed_substep_id,
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


def consume_stage_stock(
    session,
    stock: ProcedureStageStock,
    quantity: int,
) -> None:
    remaining = stock.quantity - quantity
    if remaining < 0:
        raise DomainError("stage_stock_quantity_insufficient", "当前细分工序数量不足")
    if remaining:
        stock.quantity = remaining
        return
    referencing_orders = session.scalars(
        select(WorkOrder)
        .where(WorkOrder.procedure_stage_stock_id == stock.id)
        .with_for_update()
    ).all()
    for order in referencing_orders:
        order.procedure_stage_stock_id = None
    session.flush()
    session.delete(stock)


def route_substep_output(
    session,
    *,
    production_item: ProductionItem,
    flow_context,
    flow_node_id: str,
    source_flow_node_id: str,
    substep: ProcedureSubstep,
    quantity: int,
) -> tuple[str | None, int | None, ProcedureStageStock | None]:
    procedure = session.get(Procedure, substep.procedure_id)
    if procedure is None:
        raise DomainError("procedure_not_found", "细分工序所属工艺不存在")
    if procedure.procedure_type == "standard":
        department_id = procedure_department_id(session, procedure)
        stock = upsert_stage_stock(
            session,
            production_item=production_item,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            completed_substep_id=substep.id,
            department_id=department_id,
            quantity=quantity,
        )
        session.flush()
        return flow_node_id, department_id, stock

    from services.work_order_support import move_to_node

    target = flow_context.normal_target(flow_node_id)
    department_id = move_to_node(
        session,
        production_item,
        target,
        quantity,
        flow_node_id,
    )
    return target.get("id") if target else None, department_id, None


def restore_substep_source(
    session,
    *,
    production_item: ProductionItem,
    flow_node_id: str,
    source_flow_node_id: str,
    procedure: Procedure,
    source_substep_id: int | None,
    quantity: int,
) -> int:
    department_id = procedure_department_id(session, procedure)
    if source_substep_id is None:
        upsert_repository(
            session,
            production_item=production_item,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            department_id=department_id,
            quantity=quantity,
        )
        return department_id

    source_substep = session.get(ProcedureSubstep, source_substep_id)
    if source_substep is None or source_substep.procedure_id != procedure.id:
        raise DomainError("procedure_stage_mismatch", "送检批次的来源细分工序无效")
    upsert_stage_stock(
        session,
        production_item=production_item,
        flow_node_id=flow_node_id,
        source_flow_node_id=source_flow_node_id,
        completed_substep_id=source_substep.id,
        department_id=department_id,
        quantity=quantity,
    )
    return department_id
