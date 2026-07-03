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


class ProductBomVersion(Base):
    __tablename__ = "product_bom_version"
    __table_args__ = (
        UniqueConstraint("id", "product_id"),
        UniqueConstraint("product_id", "version_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id"),
        nullable=False,
    )
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


class ProductBomItem(Base):
    __tablename__ = "product_bom_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["bom_version_id", "product_id"],
            ["product_bom_version.id", "product_bom_version.product_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "product_id"],
            ["material.id", "material.product_id"],
        ),
        UniqueConstraint("bom_version_id", "material_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bom_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="pcs")


class SemiFinishedVersion(Base):
    __tablename__ = "semi_finished_version"
    __table_args__ = (
        ForeignKeyConstraint(
            ["semi_finished_material_id", "product_id"],
            ["material.id", "material.product_id"],
        ),
        UniqueConstraint("id", "semi_finished_material_id"),
        UniqueConstraint("id", "product_id"),
        UniqueConstraint("semi_finished_material_id", "version_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    semi_finished_material_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_per_finished: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
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


class SemiFinishedInput(Base):
    __tablename__ = "semi_finished_input"
    __table_args__ = (
        ForeignKeyConstraint(
            ["semi_finished_version_id", "product_id"],
            ["semi_finished_version.id", "semi_finished_version.product_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["input_material_id", "product_id"],
            ["material.id", "material.product_id"],
        ),
        UniqueConstraint("semi_finished_version_id", "input_material_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    semi_finished_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_material_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="pcs")
