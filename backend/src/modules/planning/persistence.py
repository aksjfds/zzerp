from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ProductionPlan(Base):
    __tablename__ = "production_plan"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')",
            name="ck_production_plan_status",
        ),
        CheckConstraint("revision > 0", name="ck_production_plan_revision"),
        CheckConstraint(
            "(status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL) "
            "OR status <> 'confirmed'",
            name="ck_production_plan_confirmation",
        ),
        UniqueConstraint("customer_order_id", name="uq_production_plan_order"),
        Index("idx_production_plan_status", "status", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer_order.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    items: Mapped[list[ProductionPlanItem]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ProductionPlanItem.sort_order",
    )


class ProductionPlanItem(Base):
    __tablename__ = "production_plan_item"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('part', 'assembly', 'finished_product')",
            name="ck_production_plan_item_type",
        ),
        CheckConstraint("unit_requirement > 0", name="ck_plan_item_unit_requirement"),
        CheckConstraint("gross_required_quantity >= 0", name="ck_plan_item_gross_required"),
        CheckConstraint("estimated_inventory_quantity >= 0", name="ck_plan_item_estimated_stock"),
        CheckConstraint("net_required_quantity >= 0", name="ck_plan_item_net_required"),
        CheckConstraint("planned_production_quantity >= 0", name="ck_plan_item_planned"),
        CheckConstraint("reserved_inventory_quantity >= 0", name="ck_plan_item_reserved"),
        CheckConstraint("issued_inventory_quantity >= 0", name="ck_plan_item_issued"),
        UniqueConstraint(
            "production_plan_id",
            "customer_order_item_id",
            "identity_key",
            name="uq_production_plan_item_identity",
        ),
        Index("idx_production_plan_item_plan", "production_plan_id", "sort_order"),
        Index("idx_production_plan_item_order_item", "customer_order_item_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("production_plan.id", ondelete="CASCADE"), nullable=False
    )
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer_order_item.id", ondelete="CASCADE"), nullable=False
    )
    identity_key: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_requirement: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_inventory_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_production_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_inventory_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issued_inventory_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[ProductionPlan] = relationship(back_populates="items")
