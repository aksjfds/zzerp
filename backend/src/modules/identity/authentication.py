from database import SessionLocal
from modules.identity.persistence import User
from modules.identity.repository import find_user_by_credentials


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.username,
        "department": user.department,
        "role": user.role,
        "permissions": [
            permission.strip()
            for permission in user.permissions.split(",")
            if permission.strip()
        ],
    }


def authenticate_user(username: str, password: str) -> dict:
    with SessionLocal() as session:
        user = find_user_by_credentials(session, username, password)
        if user is None:
            raise ValueError("用户名或密码错误")
        return serialize_user(user)
