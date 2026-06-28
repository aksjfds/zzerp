from collections.abc import Callable
from datetime import datetime, timedelta
import hashlib
import secrets

from fastapi import Depends, HTTPException, Request, status

from config import get_settings
from database import SessionLocal
from models.user import User, UserSession


settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(user_id: int) -> tuple[str, str]:
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=settings.session_expire_hours)

    with SessionLocal() as session:
        session.query(UserSession).filter(UserSession.expires_at <= datetime.now()).delete()
        session.add(
            UserSession(
                user_id=user_id,
                token_hash=_hash_token(session_token),
                csrf_token=csrf_token,
                expires_at=expires_at,
            )
        )
        session.commit()

    return session_token, csrf_token


def revoke_user_session(session_token: str | None) -> None:
    if not session_token:
        return

    with SessionLocal() as session:
        user_session = (
            session.query(UserSession)
            .filter(UserSession.token_hash == _hash_token(session_token))
            .one_or_none()
        )
        if user_session is not None:
            session.delete(user_session)
            session.commit()


def get_csrf_token(session_token: str | None) -> str:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录会话无效",
        )

    with SessionLocal() as session:
        user_session = (
            session.query(UserSession)
            .filter(UserSession.token_hash == _hash_token(session_token))
            .one_or_none()
        )
        if user_session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录会话无效",
            )
        return user_session.csrf_token


def get_current_user(request: Request) -> dict:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
        )

    now = datetime.now()
    with SessionLocal() as session:
        result = (
            session.query(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .filter(UserSession.token_hash == _hash_token(session_token))
            .one_or_none()
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录会话无效",
            )

        user_session, user = result
        if user_session.expires_at <= now:
            session.delete(user_session)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录会话已过期",
            )

        return User.serialize(user)


def require_csrf(request: Request, user: dict = Depends(get_current_user)) -> dict:
    session_token = request.cookies.get(settings.session_cookie_name)
    csrf_header = request.headers.get("X-CSRF-Token")

    if not session_token or not csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")

    with SessionLocal() as session:
        user_session = (
            session.query(UserSession)
            .filter(UserSession.token_hash == _hash_token(session_token))
            .one_or_none()
        )
        if user_session is None or not secrets.compare_digest(
            user_session.csrf_token,
            csrf_header,
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")

    return user


def require_any_permission(*required: str, csrf: bool = False) -> Callable:
    dependency = require_csrf if csrf else get_current_user

    def permission_dependency(user: dict = Depends(dependency)) -> dict:
        permissions = set(user["permissions"])
        if not permissions.intersection(required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return permission_dependency


def ensure_department_access(user: dict, department: str) -> None:
    if user["department"] not in {"sys", department}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该部门")
