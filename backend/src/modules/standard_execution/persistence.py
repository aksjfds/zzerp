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


class ProcedureTagStock(Base):
    __tablename__ = "procedure_tag_stock"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_procedure_tag_stock_quantity_positive",
        ),
        UniqueConstraint(
            "production_item_id",
            "flow_node_id",
            "source_flow_node_id",
            "department_id",
            "tag_set_id",
            name="uq_procedure_tag_stock_position",
        ),
        UniqueConstraint(
            "id",
            "production_item_id",
            name="uq_procedure_tag_stock_id_production_item",
        ),
        Index(
            "idx_procedure_tag_stock_department",
            "department_id",
            "tag_set_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    tag_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure_tag_set.id"), nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkOrderPayDetail(Base):
    __tablename__ = "work_order_pay_detail"
    __table_args__ = (
        CheckConstraint(
            "tag_name = btrim(tag_name) AND tag_name <> ''",
            name="ck_work_order_pay_detail_tag_name",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_work_order_pay_detail_nonnegative",
        ),
        UniqueConstraint(
            "work_order_id",
            "procedure_tag_id",
            name="uq_work_order_pay_detail_order_tag",
        ),
        Index("idx_work_order_pay_detail_order", "work_order_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    procedure_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure_tag.id"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
