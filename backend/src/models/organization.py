from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Department(Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    department_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class Workshop(Base):
    __tablename__ = "workshop"
    __table_args__ = (
        UniqueConstraint("id", "department_id"),
        UniqueConstraint("department_id", "workshop_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    workshop_name: Mapped[str] = mapped_column(Text, nullable=False)


class Procedure(Base):
    __tablename__ = "procedure"
    __table_args__ = (UniqueConstraint("workshop_id", "procedure_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workshop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workshop.id"), nullable=False
    )
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)


class Worker(Base):
    __tablename__ = "worker"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workshop_id", "department_id"],
            ["workshop.id", "workshop.department_id"],
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    worker_name: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    workshop_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
