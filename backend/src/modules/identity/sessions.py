from datetime import timedelta
import hashlib
import secrets

from config import get_settings
from database import SessionLocal
from domain.time import utc_now
from modules.identity.persistence import UserSession
from modules.identity.authentication import serialize_user
from modules.identity.repository import (
    delete_expired_sessions,
    find_session,
    find_session_user,
)


class InvalidSession(Exception):
    pass


class ExpiredSession(InvalidSession):
    pass


settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(user_id: int) -> tuple[str, str]:
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = utc_now()
    with SessionLocal.begin() as session:
        delete_expired_sessions(session, now)
        session.add(
            UserSession(
                user_id=user_id,
                token_hash=_hash_token(session_token),
                csrf_token=csrf_token,
                expires_at=now + timedelta(hours=settings.session_expire_hours),
            )
        )
    return session_token, csrf_token


def revoke_user_session(session_token: str | None) -> None:
    if not session_token:
        return
    with SessionLocal.begin() as session:
        user_session = find_session(session, _hash_token(session_token))
        if user_session is not None:
            session.delete(user_session)


def get_csrf_token(session_token: str | None) -> str:
    if not session_token:
        raise InvalidSession
    with SessionLocal() as session:
        user_session = find_session(session, _hash_token(session_token))
        if user_session is None:
            raise InvalidSession
        if user_session.expires_at <= utc_now():
            raise ExpiredSession
        return user_session.csrf_token


def resolve_user(session_token: str | None) -> dict:
    if not session_token:
        raise InvalidSession
    now = utc_now()
    with SessionLocal.begin() as session:
        result = find_session_user(session, _hash_token(session_token))
        if result is None:
            raise InvalidSession
        user_session, user = result
        if user_session.expires_at <= now:
            session.delete(user_session)
            raise ExpiredSession
        return serialize_user(user)


def matches_csrf_token(session_token: str | None, csrf_token: str | None) -> bool:
    if not session_token or not csrf_token:
        return False
    try:
        expected = get_csrf_token(session_token)
    except InvalidSession:
        return False
    return secrets.compare_digest(expected, csrf_token)
