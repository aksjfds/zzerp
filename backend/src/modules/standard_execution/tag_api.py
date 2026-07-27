"""Narrow public API for tag configuration and tag-inventory collaboration.

This surface deliberately does not import work-order use cases, so production
core can use tag inventory rules without creating an import cycle.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.standard_execution.persistence import ProcedureTag
from modules.standard_execution.tags import (
    configured_tag_suggestions,
    consume_tag_stock,
    is_final_tag_set,
    procedure_department_id,
    restore_tag_source,
    serialize_tag,
    serialize_tag_set,
    tag_suggestions,
)


@dataclass(frozen=True, slots=True)
class ProcedureTagView:
    id: int
    procedure_id: int
    tag_name: str


def list_procedure_tag_views(
    session: Session,
    procedure_id: int,
) -> list[ProcedureTagView]:
    rows = session.execute(
        select(ProcedureTag.id, ProcedureTag.procedure_id, ProcedureTag.tag_name)
        .where(ProcedureTag.procedure_id == procedure_id)
        .order_by(ProcedureTag.tag_name, ProcedureTag.id)
    )
    return [
        ProcedureTagView(
            id=row.id,
            procedure_id=row.procedure_id,
            tag_name=row.tag_name,
        )
        for row in rows
    ]


__all__ = [
    "ProcedureTagView",
    "configured_tag_suggestions",
    "consume_tag_stock",
    "is_final_tag_set",
    "list_procedure_tag_views",
    "procedure_department_id",
    "restore_tag_source",
    "serialize_tag",
    "serialize_tag_set",
    "tag_suggestions",
]
