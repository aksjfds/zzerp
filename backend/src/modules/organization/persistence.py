from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Department(Base):
    __tablename__ = "department"
    __table_args__ = (
        UniqueConstraint("department_name", name="uq_department_name"),
        UniqueConstraint("department_code", name="uq_department_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_name: Mapped[str] = mapped_column(Text, nullable=False)
    department_code: Mapped[str] = mapped_column(Text, nullable=False)


class Workshop(Base):
    __tablename__ = "workshop"
    __table_args__ = (
        CheckConstraint(
            "input_mode IN ('single', 'multiple')",
            name="ck_workshop_input_mode",
        ),
        UniqueConstraint("id", "department_id", name="uq_workshop_department_context"),
        UniqueConstraint("department_id", "workshop_name", name="uq_workshop_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    workshop_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(Text, nullable=False, default="single")


class Procedure(Base):
    __tablename__ = "procedure"
    __table_args__ = (
        UniqueConstraint("workshop_id", "procedure_name", name="uq_procedure_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workshop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workshop.id"), nullable=False
    )
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
