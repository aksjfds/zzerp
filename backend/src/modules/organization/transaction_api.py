"""Transaction-aware organization context for collaborating modules."""

from sqlalchemy.orm import Session

from modules.organization.context_api import ProcedureContext
from modules.organization.persistence import Procedure


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


__all__ = ["load_procedure_context"]
