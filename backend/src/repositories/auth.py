from datetime import datetime

from sqlalchemy.orm import Session

from models.user import User, UserSession


def find_user_by_credentials(session: Session, username: str, password: str) -> User | None:
    return (
        session.query(User)
        .filter(User.username == username, User.password == password)
        .one_or_none()
    )


def delete_expired_sessions(session: Session, now: datetime) -> None:
    session.query(UserSession).filter(UserSession.expires_at <= now).delete()


def find_session(session: Session, token_hash: str) -> UserSession | None:
    return (
        session.query(UserSession)
        .filter(UserSession.token_hash == token_hash)
        .one_or_none()
    )


def find_session_user(session: Session, token_hash: str) -> tuple[UserSession, User] | None:
    return (
        session.query(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .filter(UserSession.token_hash == token_hash)
        .one_or_none()
    )
