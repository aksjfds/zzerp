from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Text, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, SessionLocal
from models.organization import Department


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("department.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @staticmethod
    def serialize(user: "User", department_code: str) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "name": user.username,
            "department": department_code,
            "role": user.role,
            "permissions": [
                permission.strip()
                for permission in user.permissions.split(",")
                if permission.strip()
            ],
        }

    @classmethod
    def login_selected(cls, username: str) -> dict:
        with SessionLocal() as session:
            result = session.query(cls, Department).join(
                Department,
                Department.id == cls.department_id,
            ).filter(
                cls.username == username,
                cls.active.is_(True),
                Department.active.is_(True),
            ).one_or_none()
            if result is None:
                raise ValueError("所选账号不存在或已停用")
            user, department = result
            return cls.serialize(user, department.department_code)

    @classmethod
    def list_login_accounts(cls) -> list[dict]:
        with SessionLocal() as session:
            rows = session.query(cls, Department).join(
                Department,
                Department.id == cls.department_id,
            ).filter(
                cls.active.is_(True),
                Department.active.is_(True),
            ).order_by(
                Department.id.asc(),
                cls.username.asc(),
            ).all()
            return [
                {
                    "username": user.username,
                    "department": department.department_code,
                    "department_name": department.department_name,
                    "role": user.role,
                }
                for user, department in rows
            ]

    @classmethod
    def get_by_username(cls, username: str) -> dict | None:
        with SessionLocal() as session:
            result = session.query(cls, Department).join(
                Department,
                Department.id == cls.department_id,
            ).filter(
                cls.username == username,
                cls.active.is_(True),
            ).one_or_none()
            if result is None:
                return None
            user, department = result
            return cls.serialize(user, department.department_code)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
