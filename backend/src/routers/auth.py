from fastapi import APIRouter, Depends, HTTPException, Request, Response

from config import get_settings
from models.user import User
from schemas.user import LoginPayload
from security import (
    create_user_session,
    get_csrf_token,
    get_current_user,
    require_csrf,
    revoke_user_session,
)

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.post("/login")
def login(payload: LoginPayload, response: Response):
    try:
        user = User.login(
            username=payload.username.strip(),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    session_token, csrf_token = create_user_session(user["id"])
    max_age = settings.session_expire_hours * 60 * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return {"data": user, "csrfToken": csrf_token}


@router.get("/current_user")
def current_user(request: Request, user: dict = Depends(get_current_user)):
    csrf_token = get_csrf_token(request.cookies.get(settings.session_cookie_name))
    return {"data": user, "csrfToken": csrf_token}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    _user: dict = Depends(require_csrf),
):
    revoke_user_session(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"message": "已退出登录"}
