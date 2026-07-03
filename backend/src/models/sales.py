from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
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


class CustomerOrder(Base):
    __tablename__ = "customer_order"
    __table_args__ = (
        UniqueConstraint("id", "customer_name"),
        UniqueConstraint("id", "customer_name", "purchase_order_no"),
        ForeignKeyConstraint(
            ["previous_version_id", "customer_name", "purchase_order_no"],
            [
                "customer_order.id",
                "customer_order.customer_name",
                "customer_order.purchase_order_no",
            ],
        ),
        UniqueConstraint("customer_name", "purchase_order_no", "version_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_order_no: Mapped[str] = mapped_column(Text, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    confirmed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class CustomerOrderItem(Base):
    __tablename__ = "customer_order_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_order_id", "customer_name"],
            ["customer_order.id", "customer_order.customer_name"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_customer_code_id", "product_id", "customer_name"],
            [
                "product_customer_code.id",
                "product_customer_code.product_id",
                "product_customer_code.customer_name",
            ],
        ),
        ForeignKeyConstraint(
            ["treatment_id", "customer_name"],
            ["customer_surface_treatment.id", "customer_surface_treatment.customer_name"],
        ),
        UniqueConstraint("id", "customer_order_id"),
        UniqueConstraint("id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id"),
        nullable=False,
    )
    product_customer_code_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    treatment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
