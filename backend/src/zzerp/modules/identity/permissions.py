"""Permission decoding and role-scoped authorization."""

from zzerp.errors import DomainError
from zzerp.modules.identity.contracts import (
    DEPARTMENT_WORK_ORDER_OPERATE,
    DEPARTMENT_WORK_ORDER_VIEW,
    UserResponse,
)


def parse_permissions(value: str) -> list[str]:
    return list(
        dict.fromkeys(permission for item in value.split(",") if (permission := item.strip()))
    )


def ensure_permissions(user: UserResponse, required: tuple[str, ...]) -> None:
    allowed = set(user.permissions)
    if user.department_code is not None:
        allowed.intersection_update({DEPARTMENT_WORK_ORDER_VIEW, DEPARTMENT_WORK_ORDER_OPERATE})
    elif user.role == "production":
        raise DomainError("department_required", "生产账号未关联部门", status_code=403)
    if not allowed.intersection(required):
        raise DomainError("permission_denied", "权限不足", status_code=403)
