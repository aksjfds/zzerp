from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
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
    __table_args__ = (
        CheckConstraint(
            "procedure_type IN ('standard', 'purchase_receipt')",
            name="ck_procedure_type",
        ),
        UniqueConstraint("id", "procedure_type", name="uq_procedure_id_type"),
        UniqueConstraint("workshop_id", "procedure_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workshop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workshop.id"), nullable=False
    )
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_type: Mapped[str] = mapped_column(Text, nullable=False, default="standard")


class ProcedureTag(Base):
    __tablename__ = "procedure_tag"
    __table_args__ = (
        CheckConstraint(
            "tag_name = btrim(tag_name) AND tag_name <> ''",
        ),
        UniqueConstraint("id", "procedure_id"),
        UniqueConstraint(
            "procedure_id",
            "tag_name",
            name="uq_procedure_tag_name",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    procedure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(Text, nullable=False)


class ProcedureTagSet(Base):
    __tablename__ = "procedure_tag_set"
    __table_args__ = (
        CheckConstraint("tag_key = btrim(tag_key) AND tag_key <> ''"),
        UniqueConstraint("id", "procedure_id"),
        UniqueConstraint(
            "procedure_id",
            "tag_key",
            name="uq_procedure_tag_set_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    procedure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=False
    )
    tag_key: Mapped[str] = mapped_column(Text, nullable=False)


class ProcedureTagSetMember(Base):
    __tablename__ = "procedure_tag_set_member"
    __table_args__ = (
        UniqueConstraint("tag_set_id", "tag_id"),
        Index("idx_procedure_tag_set_member_tag", "tag_id", "tag_set_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tag_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure_tag.id"), nullable=False
    )


class Worker(Base):
    __tablename__ = "worker"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workshop_id", "department_id"],
            ["workshop.id", "workshop.department_id"],
        ),
        Index("idx_worker_department_name", "department_id", "worker_name", "id"),
        Index(
            "idx_worker_workshop_department",
            "workshop_id",
            "department_id",
            postgresql_where=text("workshop_id IS NOT NULL"),
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
