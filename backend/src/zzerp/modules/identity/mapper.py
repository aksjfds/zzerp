from zzerp.modules.identity.contracts import UserResponse
from zzerp.modules.identity.permissions import parse_permissions
from zzerp.modules.identity.persistence import User


def user_profile(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.username,
        is_system=user.is_system,
        role=user.role,
        department_code=user.department_code,
        permissions=parse_permissions(user.permissions),
    )
