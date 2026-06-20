from datetime import datetime

from sqlalchemy import BigInteger, String, Text, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.database import Base, SessionLocal


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permissions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    @staticmethod
    def _serialize(user: "User") -> dict:
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

    @classmethod
    def login(cls, username: str, password: str) -> dict:
        with SessionLocal() as session:
            user = (
                session.query(cls)
                .filter(cls.username == username, cls.password == password)
                .one_or_none()
            )

            if user is None:
                raise ValueError("用户名或密码错误")

            return cls._serialize(user)

    @classmethod
    def get_by_username(cls, username: str) -> dict | None:
        with SessionLocal() as session:
            user = session.query(cls).filter(cls.username == username).one_or_none()

            if user is None:
                return None

            return cls._serialize(user)
