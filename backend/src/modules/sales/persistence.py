from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Customer(Base):
    __tablename__ = "customer"
    __table_args__ = (
        UniqueConstraint("customer_name", name="uq_customer_name"),
        Index(
            "idx_customer_name_trgm",
            "customer_name",
            postgresql_using="gin",
            postgresql_ops={"customer_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CustomerOrder(Base):
    __tablename__ = "customer_order"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'planned', 'cancelled', 'closed')",
            name="ck_customer_order_status",
        ),
        CheckConstraint("revision > 0", name="ck_customer_order_revision"),
        UniqueConstraint("customer_order_no", name="uq_customer_order_no"),
        Index("idx_customer_order_customer", "customer_id"),
        Index("idx_customer_order_status", "status", "id"),
        Index("idx_customer_order_updated", text("updated_at DESC"), text("id DESC")),
        Index(
            "idx_customer_order_no_trgm",
            "customer_order_no",
            postgresql_using="gin",
            postgresql_ops={"customer_order_no": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_no: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    items: Mapped[list[CustomerOrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="CustomerOrderItem.id"
    )
    customer: Mapped[Customer] = relationship()


class CustomerOrderItem(Base):
    __tablename__ = "customer_order_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_customer_order_item_product_version",
        ),
        UniqueConstraint(
            "id",
            "product_id",
            "product_version",
            name="uq_customer_order_item_id_version",
        ),
        UniqueConstraint(
            "id",
            "customer_order_id",
            "product_id",
            "product_version",
            name="uq_customer_order_item_context",
        ),
        UniqueConstraint(
            "customer_order_id",
            "product_id",
            "product_version",
            name="uq_customer_order_item_product_version",
        ),
        Index("idx_customer_order_item_product_version", "product_id", "product_version"),
        Index("idx_customer_order_item_order", "customer_order_id"),
        CheckConstraint("product_version > 0", name="ck_order_item_version"),
        CheckConstraint("quantity > 0", name="ck_order_item_quantity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product.id"), nullable=False
    )
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[CustomerOrder] = relationship(back_populates="items")
