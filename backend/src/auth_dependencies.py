from fastapi import Depends, HTTPException, Request, status

from config import get_settings
from modules.identity.api import (
    ExpiredSession,
    InvalidSession,
    matches_csrf_token,
    resolve_user,
)


settings = get_settings()


def get_current_user(request: Request) -> dict:
    try:
        return resolve_user(request.cookies.get(settings.session_cookie_name))
    except ExpiredSession as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录会话已过期"
        ) from exc
    except InvalidSession as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期"
        ) from exc


def get_optional_current_user(request: Request) -> dict | None:
    try:
        return get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def require_csrf(request: Request, user: dict = Depends(get_current_user)) -> dict:
    if not matches_csrf_token(
        request.cookies.get(settings.session_cookie_name),
        request.headers.get("X-CSRF-Token"),
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")
    return user
