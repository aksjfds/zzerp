"""Public query API for departments, workshops and procedures."""

from database import SessionLocal
from modules.organization.read_api import (
    get_department_views_by_codes,
    get_procedure_views,
    get_workshop_views,
    get_workshop_routes,
)


def list_departments():
    with SessionLocal() as session:
        return get_department_views_by_codes(session)


def list_workshops(department_id: int):
    with SessionLocal() as session:
        return get_workshop_views(session, department_ids={department_id})


def list_workshops_by_department_code(department_code: str):
    with SessionLocal() as session:
        departments = get_department_views_by_codes(session, {department_code})
        if not departments:
            return []
        return get_workshop_views(
            session,
            department_ids={departments[0].id},
        )


def list_workshop_routes():
    with SessionLocal() as session:
        return list(get_workshop_routes(session).values())


def list_procedures():
    with SessionLocal() as session:
        return get_procedure_views(session)


__all__ = [
    "list_departments",
    "list_procedures",
    "list_workshops",
    "list_workshop_routes",
    "list_workshops_by_department_code",
]
