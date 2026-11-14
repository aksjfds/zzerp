from collections.abc import Callable

from fastapi import Depends

from zzerp.http.dependencies import get_current_user, require_csrf
from zzerp.modules.identity.api import ensure_permissions
from zzerp.modules.identity.contracts import UserResponse


def require_any_permission(*required: str, csrf: bool = False) -> Callable:
    dependency = require_csrf if csrf else get_current_user

    def authorize(user: UserResponse = Depends(dependency)) -> UserResponse:
        ensure_permissions(user, required)
        return user

    return authorize
