from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Computed,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProductionPlan(Base):
    __tablename__ = "production_plan"
    __table_args__ = (UniqueConstraint("id", "customer_order_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_no: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        server_default=text(
            "'PP' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || "
            "LPAD(NEXTVAL('production_plan_no_seq')::TEXT, 6, '0')"
        ),
    )
    customer_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_order.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    completion_date: Mapped[date] = mapped_column(Date, nullable=False)
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
    released_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    released_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class ProductionPlanOrderItem(Base):
    __tablename__ = "production_plan_order_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["production_plan_id", "customer_order_id"],
            ["production_plan.id", "production_plan.customer_order_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["customer_order_item_id", "customer_order_id"],
            ["customer_order_item.id", "customer_order_item.customer_order_id"],
        ),
        ForeignKeyConstraint(
            ["customer_order_item_id", "product_id"],
            ["customer_order_item.id", "customer_order_item.product_id"],
        ),
        ForeignKeyConstraint(
            ["product_bom_version_id", "product_id"],
            ["product_bom_version.id", "product_bom_version.product_id"],
        ),
        UniqueConstraint("id", "product_id"),
        UniqueConstraint("production_plan_id", "customer_order_item_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_finished_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        Computed("GREATEST(planned_finished_quantity - order_required_quantity, 0)"),
        nullable=False,
    )
    product_bom_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProductionPlanMaterial(Base):
    __tablename__ = "production_plan_material"
    __table_args__ = (
        ForeignKeyConstraint(
            ["production_plan_order_item_id", "product_id"],
            ["production_plan_order_item.id", "production_plan_order_item.product_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "product_id"],
            ["material.id", "material.product_id"],
        ),
        ForeignKeyConstraint(
            ["semi_finished_version_id", "material_id"],
            [
                "semi_finished_version.id",
                "semi_finished_version.semi_finished_material_id",
            ],
        ),
        ForeignKeyConstraint(
            ["route_version_id", "material_id"],
            ["material_route_version.id", "material_route_version.material_id"],
        ),
        UniqueConstraint("production_plan_order_item_id", "material_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    theoretical_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    semi_finished_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    route_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ProductionPlanChangeLog(Base):
    __tablename__ = "production_plan_change_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_plan.id"),
        nullable=False,
    )
    changed_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    new_data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class MaterialInventory(Base):
    __tablename__ = "material_inventory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material.id"),
        nullable=False,
    )
    workshop_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workshop.id"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
