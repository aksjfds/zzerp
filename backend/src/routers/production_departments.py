from fastapi import APIRouter, Depends

from authorization import require_any_permission
from domain.permissions import DEPARTMENT_WORK_ORDER_VIEW, PLAN_VIEW, PRODUCT_VIEW
from modules.organization.api import list_departments
from schemas.organization import DepartmentResponse


router = APIRouter(prefix="/production-departments", tags=["production-departments"])


@router.get("", response_model=list[DepartmentResponse])
def department_list(user: dict = Depends(require_any_permission(PRODUCT_VIEW, PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW))):
    return list_departments(user["department_code"])


@router.get("/login-options", response_model=list[DepartmentResponse])
def login_department_list():
    return list_departments()
