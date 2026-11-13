"""Production plans reference products directly, without a version snapshot."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, TIMESTAMP, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProductionPlan(Base):
    __tablename__ = "production_plan"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_production_plan_order_no"),
        UniqueConstraint("id", "product_id", name="uq_production_plan_product"),
        ForeignKeyConstraint(
            ["product_id", "customer_id"],
            ["product.id", "product.customer_id"],
            name="fk_production_plan_product_customer",
        ),
        CheckConstraint("order_quantity > 0", name="ck_production_plan_order_quantity"),
        CheckConstraint("production_quantity > 0", name="ck_production_plan_production_quantity"),
        CheckConstraint("revision > 0", name="ck_production_plan_revision"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled', 'completed')",
            name="ck_production_plan_status",
        ),
        CheckConstraint(
            "(status IN ('confirmed', 'completed') AND confirmed_at IS NOT NULL "
            "AND confirmed_by IS NOT NULL) OR status IN ('draft', 'cancelled')",
            name="ck_production_plan_confirmation",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL AND completed_by IS NOT NULL) "
            "OR (status <> 'completed' AND completed_at IS NULL AND completed_by IS NULL)",
            name="ck_production_plan_completion",
        ),
        Index("idx_production_plan_customer", "customer_id"),
        Index("idx_production_plan_product", "product_id"),
        Index("idx_production_plan_status", "status", "id"),
        Index("idx_production_plan_updated", text("updated_at DESC"), text("id DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=False)
    order_no: Mapped[str] = mapped_column(Text, nullable=False)
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    production_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class DepartmentWorkOrder(Base):
    __tablename__ = "department_work_order"
    __table_args__ = (
        ForeignKeyConstraint(
            ["production_plan_id", "product_id"],
            ["production_plan.id", "production_plan.product_id"],
            name="fk_department_work_order_plan",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "material_node_id", "department_node_id"],
            ["product_department_route.product_id", "product_department_route.material_node_id", "product_department_route.department_node_id"],
            name="fk_department_work_order_route",
        ),
        UniqueConstraint("production_plan_id", "material_node_id", "department_node_id", name="uq_department_work_order_plan_route"),
        CheckConstraint("task_quantity > 0", name="ck_department_work_order_quantity"),
        Index("idx_department_work_order_route", "product_id", "material_node_id", "department_node_id"),
        Index("idx_department_work_order_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    department_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class DepartmentWorkOrderMovement(Base):
    __tablename__ = "department_work_order_movement"
    __table_args__ = (
        UniqueConstraint("work_order_id", "request_id", name="uq_department_movement_request"),
        CheckConstraint("direction IN ('receipt', 'issue')", name="ck_department_movement_direction"),
        CheckConstraint("quantity > 0 AND quantity <= 9007199254740991", name="ck_department_movement_quantity"),
        Index("idx_department_movement_order", "work_order_id", "created_at", "id"),
        Index("idx_department_movement_actor", "actor_user_id"),
        Index("idx_department_movement_ticket", "ticket_id"),
        CheckConstraint("receipt_source IS DISTINCT FROM 'external' OR note ~ '[^[:space:]]'", name="ck_unattributed_receipt_note"),
        CheckConstraint("(direction = 'issue' AND receipt_source IS NULL AND ticket_id IS NULL AND input_material_node_id IS NULL) OR "
                        "(direction = 'receipt' AND receipt_source IS NOT NULL AND input_material_node_id IS NOT NULL AND "
                        "((receipt_source = 'external' AND ticket_id IS NULL) OR (receipt_source = 'ticket' AND ticket_id IS NOT NULL)))",
                        name="ck_department_movement_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order.id"), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    receipt_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("department_handoff_ticket.id"), nullable=True)
    input_material_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class DepartmentHandoffTicket(Base):
    __tablename__ = "department_handoff_ticket"
    __table_args__ = (
        UniqueConstraint("issue_movement_id", name="uq_handoff_issue"),
        Index("idx_handoff_target", "target_work_order_id", "id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issue_movement_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order_movement.id"), nullable=False)
    target_work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order.id"), nullable=False)


class DepartmentMovementReceiptLink(Base):
    __tablename__ = "department_movement_receipt_link"
    issue_movement_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order_movement.id"), primary_key=True)
    receipt_movement_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order_movement.id"), primary_key=True)
    __table_args__ = (Index("idx_movement_link_receipt", "receipt_movement_id"),)
