from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from zzerp.modules.identity.persistence import User, UserSession


def find_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def delete_expired_sessions(session: Session, now: datetime) -> None:
    session.execute(delete(UserSession).where(UserSession.expires_at <= now))


def find_session_user(session: Session, token_hash: str) -> tuple[UserSession, User] | None:
    result = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_hash),
    ).one_or_none()
    return (result[0], result[1]) if result is not None else None
