"""Public query API for departments, workshops, procedures and tags."""

from database import SessionLocal
from modules.organization.read_api import (
    get_department_views_by_codes,
    get_procedure_views,
    get_workshop_views,
)
from modules.standard_execution.tag_api import list_procedure_tag_views


def list_departments():
    with SessionLocal() as session:
        return get_department_views_by_codes(session)


def list_workshops(department_id: int):
    with SessionLocal() as session:
        return get_workshop_views(session, department_ids={department_id})


def list_procedures():
    with SessionLocal() as session:
        return get_procedure_views(session)


def list_procedure_tags(procedure_id: int):
    with SessionLocal() as session:
        return list_procedure_tag_views(session, procedure_id)


__all__ = [
    "list_departments",
    "list_procedure_tags",
    "list_procedures",
    "list_workshops",
]
