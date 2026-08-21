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


class ProcedurePrice(Base):
    __tablename__ = "procedure_price"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_procedure_price_nonnegative"),
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            ondelete="CASCADE",
            name="fk_procedure_price_product_version",
        ),
        UniqueConstraint(
            "product_id",
            "product_version",
            "material_key",
            "flow_node_id",
            "procedure_id",
            name="uq_procedure_price_scope",
        ),
        Index(
            "idx_procedure_price_scope",
            "procedure_id",
            "product_id",
            "product_version",
            "flow_node_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    material_key: Mapped[str] = mapped_column(Text, nullable=False)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=False
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class WorkOrderPayDetail(Base):
    __tablename__ = "work_order_pay_detail"
    __table_args__ = (
        CheckConstraint(
            "procedure_name = btrim(procedure_name) AND procedure_name <> ''",
            name="ck_work_order_pay_detail_procedure_name",
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_work_order_pay_detail_nonnegative",
        ),
        UniqueConstraint("work_order_id", name="uq_work_order_pay_detail_order"),
        Index("idx_work_order_pay_detail_procedure", "procedure_id", "work_order_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_order.id", ondelete="CASCADE"), nullable=False
    )
    procedure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("procedure.id"), nullable=False
    )
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
