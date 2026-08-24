from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from auth_dependencies import get_current_user, require_csrf
from domain.identity import can_access_department


def require_any_permission(*required: str, csrf: bool = False) -> Callable:
    dependency = require_csrf if csrf else get_current_user

    def permission_dependency(user: dict = Depends(dependency)) -> dict:
        if not set(user["permissions"]).intersection(required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return permission_dependency


def ensure_department_access(user: dict, department: str) -> None:
    if not can_access_department(
        user["department"],
        user["is_system"],
        department,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该部门")
