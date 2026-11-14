from datetime import timedelta

from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.identity.contracts import LoginResult
from zzerp.modules.identity.mapper import user_profile
from zzerp.modules.identity.passwords import DUMMY_HASH, verify_password
from zzerp.modules.identity.repository import find_user
from zzerp.modules.identity.sessions import create_session


def login_user(
    session: Session,
    username: str,
    password: str,
    *,
    lifetime: timedelta,
) -> LoginResult:
    user = find_user(session, username.strip())
    verified = verify_password(password, user.password if user is not None else DUMMY_HASH)
    if user is None or not verified:
        raise DomainError("invalid_credentials", "用户名或密码错误", status_code=401)
    return create_session(session, user_profile(user), lifetime=lifetime)
