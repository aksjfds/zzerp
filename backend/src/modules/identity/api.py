"""Public in-process API for authentication and user sessions."""

from modules.identity.authentication import authenticate_user, serialize_user
from modules.identity.sessions import (
    ExpiredSession,
    InvalidSession,
    create_user_session,
    get_csrf_token,
    matches_csrf_token,
    resolve_user,
    revoke_user_session,
)


__all__ = [
    "ExpiredSession",
    "InvalidSession",
    "authenticate_user",
    "create_user_session",
    "get_csrf_token",
    "matches_csrf_token",
    "resolve_user",
    "revoke_user_session",
    "serialize_user",
]
