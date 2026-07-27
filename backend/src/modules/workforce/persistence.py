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
