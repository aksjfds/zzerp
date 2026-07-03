from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Department(Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    department_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    department_type: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )


class Workshop(Base):
    __tablename__ = "workshop"
    __table_args__ = (
        UniqueConstraint("id", "department_id"),
        UniqueConstraint("department_id", "workshop_code"),
        UniqueConstraint("department_id", "workshop_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("department.id"),
        nullable=False,
    )
    workshop_code: Mapped[str] = mapped_column(Text, nullable=False)
    workshop_name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )


class UserWorkshopPermission(Base):
    __tablename__ = "user_workshop_permission"
    __table_args__ = (UniqueConstraint("user_id", "workshop_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workshop_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workshop.id"),
        nullable=False,
    )
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_create_work_order: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    can_report: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
