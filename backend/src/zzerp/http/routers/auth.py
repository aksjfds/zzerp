from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response

from zzerp.config import Settings
from zzerp.database import Database
from zzerp.http.dependencies import (
    get_database,
    get_optional_current_session,
    get_settings,
    require_csrf,
)
from zzerp.modules.identity import api as identity
from zzerp.modules.identity.contracts import (
    CurrentUserResponse,
    LoginPayload,
    LoginResponse,
    MessageResponse,
    ResolvedSession,
    UserResponse,
)

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginPayload,
    response: Response,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    result = database.command(
        identity.login_user,
        payload.username,
        payload.password,
        lifetime=timedelta(hours=settings.session_expire_hours),
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        max_age=settings.session_expire_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return {"data": result.user, "csrfToken": result.csrf_token}


@router.get("/current_user", response_model=CurrentUserResponse, response_model_exclude_none=True)
def current_user(resolved: ResolvedSession | None = Depends(get_optional_current_session)):
    if resolved is None:
        return {"data": None}
    return {"data": resolved.user, "csrfToken": resolved.csrf_token}


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    _user: UserResponse = Depends(require_csrf),
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    database.command(
        identity.revoke_user_session, request.cookies.get(settings.session_cookie_name)
    )
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"message": "已退出登录"}
