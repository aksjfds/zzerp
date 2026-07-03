from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MaterialRouteVersion(Base):
    __tablename__ = "material_route_version"
    __table_args__ = (
        ForeignKeyConstraint(
            ["material_id", "product_id"],
            ["material.id", "material.product_id"],
        ),
        UniqueConstraint("id", "material_id"),
        UniqueConstraint("material_id", "version_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    published_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class MaterialRouteStep(Base):
    __tablename__ = "material_route_step"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workshop_id", "department_id"],
            ["workshop.id", "workshop.department_id"],
        ),
        UniqueConstraint("route_version_id", "sequence_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    route_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_route_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("department.id"),
        nullable=True,
    )
    workshop_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
