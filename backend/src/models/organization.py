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


class ProcedureTagPrice(Base):
    __tablename__ = "procedure_tag_price"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_procedure_tag_price_nonnegative"),
        ForeignKeyConstraint(
            ["procedure_tag_id", "procedure_id"],
            ["procedure_tag.id", "procedure_tag.procedure_id"],
            name="fk_procedure_tag_price_tag",
        ),
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            ondelete="CASCADE",
            name="fk_procedure_tag_price_product_version",
        ),
        UniqueConstraint(
            "product_id",
            "product_version",
            "origin_flow_node_id",
            "procedure_tag_id",
            name="uq_procedure_tag_price_part_tag",
        ),
        Index(
            "idx_procedure_tag_price_procedure",
            "procedure_id",
            "product_id",
            "product_version",
            "origin_flow_node_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    procedure_tag_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


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
            "uq_worker_workshop_name",
            "department_id",
            "workshop_id",
            "worker_name",
            unique=True,
            postgresql_where=text("workshop_id IS NOT NULL"),
        ),
        Index(
            "uq_worker_department_direct_name",
            "department_id",
            "worker_name",
            unique=True,
            postgresql_where=text("workshop_id IS NULL"),
        ),
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
