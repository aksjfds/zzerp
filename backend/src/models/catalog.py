from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class CatalogProduct(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factory_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    next_semi_finished_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
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
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )


class ProductCustomerCode(Base):
    __tablename__ = "product_customer_code"
    __table_args__ = (
        UniqueConstraint("id", "product_id"),
        UniqueConstraint("id", "product_id", "customer_name"),
        UniqueConstraint("id", "customer_name"),
        UniqueConstraint("customer_name", "customer_product_code"),
        UniqueConstraint("product_id", "customer_name", "customer_product_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id"),
        nullable=False,
    )
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    customer_product_code: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )


class CustomerSurfaceTreatment(Base):
    __tablename__ = "customer_surface_treatment"
    __table_args__ = (
        UniqueConstraint("id", "customer_name"),
        UniqueConstraint("customer_name", "treatment_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    treatment_name: Mapped[str] = mapped_column(Text, nullable=False)
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


class ProductCustomerTreatment(Base):
    __tablename__ = "product_customer_treatment"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_customer_code_id", "customer_name"],
            ["product_customer_code.id", "product_customer_code.customer_name"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["treatment_id", "customer_name"],
            ["customer_surface_treatment.id", "customer_surface_treatment.customer_name"],
        ),
        UniqueConstraint("product_customer_code_id", "treatment_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_customer_code_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    treatment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)


class Material(Base):
    __tablename__ = "material"
    __table_args__ = (UniqueConstraint("id", "product_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id"),
        nullable=False,
    )
    material_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    material_name: Mapped[str] = mapped_column(Text, nullable=False)
    material_type: Mapped[str] = mapped_column(Text, nullable=False)
    material_grade: Mapped[str | None] = mapped_column(Text, nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ProductReleasedSemiNumber(Base):
    __tablename__ = "product_released_semi_number"
    __table_args__ = (UniqueConstraint("product_id", "sequence_no"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
