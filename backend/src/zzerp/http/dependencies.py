"""Request-scoped identity and access to application-owned resources."""

import secrets

from fastapi import Depends, Request

from zzerp.config import Settings
from zzerp.database import Database
from zzerp.errors import DomainError
from zzerp.modules.identity import api as identity
from zzerp.modules.identity.contracts import ResolvedSession, UserResponse


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_session(
    request: Request,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ResolvedSession:
    return database.query(
        identity.resolve_session, request.cookies.get(settings.session_cookie_name)
    )


def get_optional_current_session(
    request: Request,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ResolvedSession | None:
    try:
        return get_current_session(request, database, settings)
    except DomainError as exc:
        if exc.status_code == 401:
            return None
        raise


def get_current_user(resolved: ResolvedSession = Depends(get_current_session)) -> UserResponse:
    return resolved.user


def require_csrf(
    request: Request,
    resolved: ResolvedSession = Depends(get_current_session),
) -> UserResponse:
    token = request.headers.get("X-CSRF-Token")
    if not token or not secrets.compare_digest(resolved.csrf_token, token):
        raise DomainError("csrf_invalid", "CSRF校验失败", status_code=403)
    return resolved.user
