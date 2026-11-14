"""Session reads expose the typed identity and CSRF context in one query."""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.identity.contracts import LoginResult, ResolvedSession, UserResponse
from zzerp.modules.identity.mapper import user_profile
from zzerp.modules.identity.persistence import UserSession
from zzerp.modules.identity.repository import delete_expired_sessions, find_session_user
from zzerp.time import utc_now


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    session: Session,
    user: UserResponse,
    *,
    lifetime: timedelta,
) -> LoginResult:
    now = utc_now()
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    expires_at = now + lifetime
    delete_expired_sessions(session, now)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            csrf_token=csrf,
            expires_at=expires_at,
        )
    )
    session.flush()
    return LoginResult(user, token, csrf, expires_at)


def revoke_user_session(session: Session, token: str | None) -> None:
    if token:
        session.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))


def resolve_session(session: Session, token: str | None) -> ResolvedSession:
    if not token:
        raise DomainError("session_required", "未登录或登录已过期", status_code=401)
    result = find_session_user(session, _hash_token(token))
    if result is None:
        raise DomainError("session_required", "未登录或登录已过期", status_code=401)
    stored, user = result
    if stored.expires_at <= utc_now():
        raise DomainError("session_expired", "登录会话已过期", status_code=401)
    return ResolvedSession(user_profile(user), stored.csrf_token, stored.expires_at)
