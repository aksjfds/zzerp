from sqlalchemy import select

from zzerp.modules.identity.persistence import User


def usernames_by_ids(session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    return dict(session.execute(select(User.id, User.username).where(User.id.in_(user_ids))).all())
