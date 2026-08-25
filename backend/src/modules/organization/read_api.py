"""Immutable read projections exposed by the organization module."""

from dataclasses import dataclass
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.organization.persistence import Department, Procedure, Workshop


@dataclass(frozen=True, slots=True)
class DepartmentView:
    id: int
    department_name: str
    department_code: str


@dataclass(frozen=True, slots=True)
class WorkshopView:
    id: int
    department_id: int
    workshop_name: str
    input_mode: str


@dataclass(frozen=True, slots=True)
class WorkshopRoute:
    workshop_id: int
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    input_mode: str

    @property
    def id(self) -> int:
        return self.workshop_id


@dataclass(frozen=True, slots=True)
class ProcedureView:
    id: int
    workshop_id: int
    department_name: str
    department_code: str
    procedure_name: str


@dataclass(frozen=True, slots=True)
class ProcedureRoute:
    procedure_id: int
    procedure_name: str
    workshop_id: int
    department_id: int

    @property
    def id(self) -> int:
        return self.procedure_id


def get_department_views_by_codes(
    session: Session,
    department_codes: Collection[str] | None = None,
) -> list[DepartmentView]:
    if department_codes is not None and not department_codes:
        return []
    statement = (
        select(
            Department.id,
            Department.department_name,
            Department.department_code,
        )
    )
    if department_codes is not None:
        statement = statement.where(
            Department.department_code.in_(department_codes)
        )
    rows = session.execute(statement.order_by(Department.id))
    return [
        DepartmentView(
            id=row.id,
            department_name=row.department_name,
            department_code=row.department_code,
        )
        for row in rows
    ]


def get_department_views_by_ids(
    session: Session,
    department_ids: Collection[int],
) -> list[DepartmentView]:
    if not department_ids:
        return []
    rows = session.execute(
        select(
            Department.id,
            Department.department_name,
            Department.department_code,
        )
        .where(Department.id.in_(department_ids))
        .order_by(Department.id)
    )
    return [
        DepartmentView(
            id=row.id,
            department_name=row.department_name,
            department_code=row.department_code,
        )
        for row in rows
    ]


def get_workshop_views(
    session: Session,
    *,
    department_ids: Collection[int] | None = None,
    workshop_ids: Collection[int] | None = None,
) -> list[WorkshopView]:
    statement = select(
        Workshop.id,
        Workshop.department_id,
        Workshop.workshop_name,
        Workshop.input_mode,
    )
    if department_ids is not None:
        if not department_ids:
            return []
        statement = statement.where(Workshop.department_id.in_(department_ids))
    if workshop_ids is not None:
        if not workshop_ids:
            return []
        statement = statement.where(Workshop.id.in_(workshop_ids))
    rows = session.execute(
        statement.order_by(Workshop.workshop_name, Workshop.id)
    )
    return [
        WorkshopView(
            id=row.id,
            department_id=row.department_id,
            workshop_name=row.workshop_name,
            input_mode=row.input_mode,
        )
        for row in rows
    ]


def get_workshop_routes(
    session: Session,
    workshop_ids: Collection[int] | None = None,
) -> dict[int, WorkshopRoute]:
    if workshop_ids is not None and not workshop_ids:
        return {}
    statement = (
        select(
            Workshop.id,
            Workshop.workshop_name,
            Workshop.department_id,
            Workshop.input_mode,
            Department.department_name,
            Department.department_code,
        )
        .join(Department, Department.id == Workshop.department_id)
    )
    if workshop_ids is not None:
        statement = statement.where(Workshop.id.in_(workshop_ids))
    rows = session.execute(statement.order_by(Department.id, Workshop.id))
    return {
        row.id: WorkshopRoute(
            workshop_id=row.id,
            workshop_name=row.workshop_name,
            department_id=row.department_id,
            department_name=row.department_name,
            department_code=row.department_code,
            input_mode=row.input_mode,
        )
        for row in rows
    }


def get_procedure_views(session: Session) -> list[ProcedureView]:
    rows = session.execute(
        select(
            Procedure.id,
            Procedure.workshop_id,
            Department.department_name,
            Department.department_code,
            Procedure.procedure_name,
        )
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .join(Department, Department.id == Workshop.department_id)
        .order_by(Department.id, Procedure.id)
    )
    return [
        ProcedureView(
            id=row.id,
            workshop_id=row.workshop_id,
            department_name=row.department_name,
            department_code=row.department_code,
            procedure_name=row.procedure_name,
        )
        for row in rows
    ]


def get_procedure_routes(
    session: Session,
    procedure_ids: set[int],
) -> dict[int, ProcedureRoute]:
    if not procedure_ids:
        return {}
    rows = session.execute(
        select(
            Procedure.id,
            Procedure.procedure_name,
            Procedure.workshop_id,
            Workshop.department_id,
        )
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .where(Procedure.id.in_(procedure_ids))
    )
    return {
        row.id: ProcedureRoute(
            procedure_id=row.id,
            procedure_name=row.procedure_name,
            workshop_id=row.workshop_id,
            department_id=row.department_id,
        )
        for row in rows
    }


def get_department_procedure_routes(
    session: Session,
    department_id: int,
) -> list[ProcedureRoute]:
    statement = (
        select(
            Procedure.id,
            Procedure.procedure_name,
            Procedure.workshop_id,
            Workshop.department_id,
        )
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .where(Workshop.department_id == department_id)
    )
    rows = session.execute(
        statement.order_by(Procedure.procedure_name, Procedure.id)
    )
    return [
        ProcedureRoute(
            procedure_id=row.id,
            procedure_name=row.procedure_name,
            workshop_id=row.workshop_id,
            department_id=row.department_id,
        )
        for row in rows
    ]


def get_department_ids_by_codes(
    session: Session,
    department_codes: set[str],
) -> dict[str, int]:
    if not department_codes:
        return {}
    return {
        code: department_id
        for code, department_id in session.execute(
            select(Department.department_code, Department.id).where(
                Department.department_code.in_(department_codes)
            )
        )
    }


__all__ = [
    "DepartmentView",
    "ProcedureView",
    "ProcedureRoute",
    "WorkshopView",
    "WorkshopRoute",
    "get_department_ids_by_codes",
    "get_department_procedure_routes",
    "get_department_views_by_codes",
    "get_department_views_by_ids",
    "get_procedure_views",
    "get_procedure_routes",
    "get_workshop_views",
    "get_workshop_routes",
]
