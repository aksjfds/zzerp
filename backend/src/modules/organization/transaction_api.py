"""Transaction-aware organization context for collaborating modules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.organization.context_api import ProcedureContext
from modules.organization.persistence import Procedure, Workshop
from modules.errors import DomainError


def load_procedure_context(
    session: Session,
    procedure_id: int,
    *,
    for_update: bool = False,
) -> ProcedureContext | None:
    return session.get(
        Procedure,
        procedure_id,
        with_for_update=for_update,
    )


def resolve_workshop_procedure(
    session: Session,
    *,
    workshop_id: int,
    procedure_id: int | None,
    procedure_name: str | None,
    required_input_mode: str,
) -> ProcedureContext:
    workshop = session.get(Workshop, workshop_id)
    if workshop is None:
        raise DomainError("workshop_not_found", "当前流程车间不存在")
    if workshop.input_mode != required_input_mode:
        raise DomainError(
            "workshop_input_mode_invalid",
            "当前车间不适用于所选流程节点",
        )
    normalized_name = (procedure_name or "").strip()
    if procedure_id is not None:
        procedure = session.get(Procedure, procedure_id, with_for_update=True)
        if procedure is None or procedure.workshop_id != workshop_id:
            raise DomainError("procedure_workshop_invalid", "所选工艺不属于当前车间")
        return procedure
    if not normalized_name:
        raise DomainError("procedure_required", "请选择已有工艺或填写新工艺")
    if len(normalized_name) > 200:
        raise DomainError("procedure_name_too_long", "工艺名称不能超过200个字符")
    procedure = session.scalar(
        select(Procedure)
        .where(
            Procedure.workshop_id == workshop_id,
            Procedure.procedure_name == normalized_name,
        )
        .with_for_update()
    )
    if procedure is not None:
        return procedure
    procedure = Procedure(
        workshop_id=workshop_id,
        procedure_name=normalized_name,
    )
    session.add(procedure)
    session.flush()
    return procedure


def delete_procedure(session: Session, procedure_id: int) -> bool:
    procedure = session.get(Procedure, procedure_id, with_for_update=True)
    if procedure is None:
        return False
    session.delete(procedure)
    return True


__all__ = [
    "delete_procedure",
    "load_procedure_context",
    "resolve_workshop_procedure",
]
