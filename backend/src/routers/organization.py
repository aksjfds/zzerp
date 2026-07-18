from fastapi import APIRouter, Depends
from sqlalchemy import select

from authorization import require_any_permission
from database import SessionLocal
from domain.permissions import PRODUCT_VIEW
from models.organization import Department, Procedure, ProcedureTag, Workshop
from schemas.organization import (
    DepartmentResponse,
    ProcedureResponse,
    ProcedureTagResponse,
    WorkshopResponse,
)


router = APIRouter(tags=["organization"])


@router.get("/departments", response_model=list[DepartmentResponse])
def departments(_: dict = Depends(require_any_permission(PRODUCT_VIEW, "order:view"))):
    with SessionLocal() as session:
        return session.scalars(select(Department).order_by(Department.id)).all()


@router.get(
    "/departments/{department_id}/workshops", response_model=list[WorkshopResponse]
)
def workshops(
    department_id: int,
    _: dict = Depends(require_any_permission(PRODUCT_VIEW, "order:view")),
):
    with SessionLocal() as session:
        return session.scalars(
            select(Workshop)
            .where(Workshop.department_id == department_id)
            .order_by(Workshop.id)
        ).all()


@router.get("/procedures", response_model=list[ProcedureResponse])
def procedures(_: dict = Depends(require_any_permission(PRODUCT_VIEW))):
    with SessionLocal() as session:
        return session.scalars(select(Procedure).order_by(Procedure.id)).all()


@router.get(
    "/procedures/{procedure_id}/tags",
    response_model=list[ProcedureTagResponse],
)
def procedure_tags(
    procedure_id: int,
    _: dict = Depends(require_any_permission(PRODUCT_VIEW, "production:view")),
):
    with SessionLocal() as session:
        return session.scalars(
            select(ProcedureTag)
            .where(ProcedureTag.procedure_id == procedure_id)
            .order_by(ProcedureTag.tag_name, ProcedureTag.id)
        ).all()
