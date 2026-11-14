from fastapi import APIRouter, Depends

from zzerp.database import Database
from zzerp.http.authorization import require_any_permission
from zzerp.http.dependencies import get_database
from zzerp.modules.identity.contracts import (
    DEPARTMENT_WORK_ORDER_VIEW,
    PLAN_VIEW,
    PRODUCT_VIEW,
    UserResponse,
)
from zzerp.modules.organization.api import list_departments
from zzerp.modules.organization.contracts import DepartmentResponse

router = APIRouter(prefix="/production-departments", tags=["production-departments"])


@router.get("", response_model=list[DepartmentResponse])
def department_list(
    user: UserResponse = Depends(
        require_any_permission(PRODUCT_VIEW, PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)
    ),
    database: Database = Depends(get_database),
):
    return database.query(list_departments, user.department_code)


@router.get("/login-options", response_model=list[DepartmentResponse])
def login_department_list(
    database: Database = Depends(get_database),
):
    return database.query(
        list_departments,
    )
