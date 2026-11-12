from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from auth_dependencies import get_current_user, require_csrf
from domain.permissions import DEPARTMENT_WORK_ORDER_OPERATE, DEPARTMENT_WORK_ORDER_VIEW


def require_any_permission(*required: str, csrf: bool = False) -> Callable:
    dependency = require_csrf if csrf else get_current_user

    def permission_dependency(user: dict = Depends(dependency)) -> dict:
        allowed = set(user["permissions"])
        if user["department_code"] is not None:
            allowed.intersection_update({DEPARTMENT_WORK_ORDER_VIEW, DEPARTMENT_WORK_ORDER_OPERATE})
        elif user["role"] == "production":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="生产账号未关联部门")
        if not allowed.intersection(required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return permission_dependency
