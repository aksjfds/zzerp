"""Plan-owned product snapshots, route projections and production history."""

from datetime import date, datetime
from uuid import UUID

from database import Base
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

JSON_TYPE = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class PurchaseOrder(Base):
    __tablename__ = 'purchase_order'
    __table_args__ = (
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_purchase_order_quantity'),
        UniqueConstraint('request_id', name='uq_purchase_order_request'),
        Index('idx_purchase_order_work_order', 'work_order_id', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseReceipt(Base):
    __tablename__ = 'purchase_receipt'
    __table_args__ = (
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_purchase_receipt_quantity'),
        UniqueConstraint('request_id', name='uq_purchase_receipt_request'),
        Index('uq_purchase_receipt_order', 'purchase_order_id', unique=True, postgresql_where=text('revoked_at IS NULL')),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('purchase_order.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutsourceDispatch(Base):
    __tablename__ = 'outsource_dispatch'
    __table_args__ = (
        CheckConstraint("process IN ('etching', 'plating')", name='ck_outsource_process'),
        CheckConstraint("length(btrim(vendor)) BETWEEN 1 AND 100 AND vendor ~ '[^[:space:]]'", name='ck_outsource_vendor'),
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_outsource_dispatch_quantity'),
        UniqueConstraint('request_id', name='uq_outsource_dispatch_request'),
        Index('idx_outsource_dispatch_receipt', 'receipt_id', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order_movement.id'), nullable=False)
    process: Mapped[str] = mapped_column(Text, nullable=False)
    vendor: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class OutsourceReturn(Base):
    __tablename__ = 'outsource_return'
    __table_args__ = (
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_outsource_return_quantity'),
        UniqueConstraint('request_id', name='uq_outsource_return_request'),
        Index('idx_outsource_return_dispatch', 'dispatch_id', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outsource_dispatch.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ProductionPlan(Base):
    __tablename__ = "production_plan"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_production_plan_order_no"),
        UniqueConstraint("id", "customer_id", name="uq_production_plan_customer"),
        CheckConstraint("revision > 0", name="ck_production_plan_revision"),
        CheckConstraint("delivery_date >= order_date", name="ck_production_plan_dates"),
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
        Index("idx_production_plan_status", "status", "id"),
        Index("idx_production_plan_updated", text("updated_at DESC"), text("id DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=False)
    order_no: Mapped[str] = mapped_column(Text, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ProductionPlanItem(Base):
    __tablename__ = "production_plan_item"
    __table_args__ = (
        ForeignKeyConstraint(["production_plan_id", "customer_id"],
            ["production_plan.id", "production_plan.customer_id"],
            name="fk_production_plan_item_plan", ondelete="CASCADE"),
        ForeignKeyConstraint(["product_id"], ["product.id"], name="fk_production_plan_item_product"),
        CheckConstraint("source_version > 0", name="ck_plan_item_source_version"),
        CheckConstraint("length(btrim(source_version_value)) BETWEEN 1 AND 100", name="ck_plan_item_version_value"),
        CheckConstraint("order_quantity > 0", name="ck_production_plan_item_order_quantity"),
        CheckConstraint("production_quantity > 0", name="ck_production_plan_item_production_quantity"),
        Index("idx_production_plan_item_product", "product_id"),
    )
    production_plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    production_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version_value: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    factory_code: Mapped[str] = mapped_column(Text, nullable=False)
    customer_code: Mapped[str] = mapped_column(Text, nullable=False)
    bom_snapshot: Mapped[list[dict]] = mapped_column(JSON_TYPE, nullable=False)
    process_flow_snapshot: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)



class PlanProductRoute(Base):
    __tablename__ = "plan_product_route"
    __table_args__ = (
        ForeignKeyConstraint(["production_plan_id", "product_id"],
            ["production_plan_item.production_plan_id", "production_plan_item.product_id"],
            name="fk_plan_product_route_item", ondelete="CASCADE"),
        CheckConstraint("unit_requirement > 0", name="ck_plan_product_route_quantity"),
        Index("idx_plan_product_route_department", "department_code", "production_plan_id", "product_id"),
    )
    production_plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    material_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    department_node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    department_code: Mapped[str] = mapped_column(Text, ForeignKey("production_department.code"), nullable=False)
    part_no: Mapped[str] = mapped_column(Text, nullable=False)
    part_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_requirement: Mapped[int] = mapped_column(Integer, nullable=False)


class DepartmentWorkOrder(Base):
    __tablename__ = "department_work_order"
    __table_args__ = (
        ForeignKeyConstraint(
            ["production_plan_id", "product_id"],
            ["production_plan_item.production_plan_id", "production_plan_item.product_id"],
            name="fk_department_work_order_plan",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["production_plan_id", "product_id", "material_node_id", "department_node_id"],
            ["plan_product_route.production_plan_id", "plan_product_route.product_id", "plan_product_route.material_node_id", "plan_product_route.department_node_id"],
            name="fk_department_work_order_route",
        ),
        UniqueConstraint("production_plan_id", "product_id", "material_node_id", "department_node_id", name="uq_department_work_order_plan_route"),
        CheckConstraint("task_quantity > 0", name="ck_department_work_order_quantity"),
        CheckConstraint("schedule_revision > 0", name="ck_department_work_order_schedule_revision"),
        Index("idx_department_work_order_route", "product_id", "material_node_id", "department_node_id"),
        Index("idx_department_work_order_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    department_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    schedule_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class DepartmentWorkOrderMovement(Base):
    __tablename__ = "department_work_order_movement"
    __table_args__ = (
        CheckConstraint("(document_type = 'normal' AND piecework_process = '') OR (document_type = 'piecework' AND length(btrim(piecework_process)) <= 100)", name='ck_movement_piecework_process'),
        CheckConstraint("(document_type = 'normal' AND worker_name = '') OR (document_type = 'piecework' AND direction = 'issue' AND length(worker_name) BETWEEN 1 AND 100 AND worker_name ~ '[^[:space:]]')", name="ck_movement_piecework"),
        UniqueConstraint("work_order_id", "request_id", name="uq_department_movement_request"),
        CheckConstraint("direction IN ('receipt', 'issue')", name="ck_department_movement_direction"),
        CheckConstraint("quantity > 0 AND quantity <= 9007199254740991", name="ck_department_movement_quantity"),
        Index("idx_department_movement_order", "work_order_id", "created_at", "id"),
        Index("idx_department_movement_actor", "actor_user_id"),
        Index('idx_movement_piecework_worker', 'worker_name', 'id', postgresql_where=text("document_type = 'piecework'")),
        Index("uq_department_movement_ticket", "ticket_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
        Index("uq_department_movement_warehouse_pick", "warehouse_pick_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
        CheckConstraint("(direction = 'issue' AND receipt_source IS NULL AND ticket_id IS NULL AND input_material_node_id IS NULL) OR "
                        "(direction = 'receipt' AND receipt_source IS NOT NULL AND input_material_node_id IS NOT NULL AND "
                        "((receipt_source = 'ticket' AND ticket_id IS NOT NULL) OR (receipt_source = 'warehouse' AND ticket_id IS NULL)))",
                        name="ck_department_movement_source"),
        CheckConstraint("(warehouse_pick_id IS NOT NULL) = (receipt_source IS NOT DISTINCT FROM 'warehouse')", name="ck_department_movement_warehouse_pick"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(Text, nullable=False, default='normal', server_default=text("'normal'"))
    worker_name: Mapped[str] = mapped_column(Text, nullable=False, default='', server_default=text("''"))
    piecework_process: Mapped[str] = mapped_column(Text, nullable=False, default='', server_default=text("''"))
    work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order.id"), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    receipt_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("department_handoff_ticket.id"), nullable=True)
    warehouse_pick_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse_pick.id", name="fk_department_movement_warehouse_pick", use_alter=True), nullable=True)
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


class QcInspection(Base):
    __tablename__ = "qc_inspection"
    __table_args__ = (
        CheckConstraint("(rework_quantity = 0 AND repair_kind IS NULL AND repair_worker_name = '') OR (rework_quantity > 0 AND repair_kind IS NOT NULL AND repair_kind IN ('original', 'cross') AND (repair_kind = 'original' OR repair_worker_name = ''))", name="ck_qc_repair_kind"),
        Index("uq_qc_inspection_ticket", "source_ticket_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
        Index("uq_qc_inspection_return", "source_return_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
        Index("uq_qc_inspection_pick", "source_pick_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
        UniqueConstraint("request_id", name="uq_qc_inspection_request"),
        CheckConstraint("(CASE WHEN source_ticket_id IS NULL THEN 0 ELSE 1 END + CASE WHEN source_return_id IS NULL THEN 0 ELSE 1 END + CASE WHEN source_pick_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_qc_inspection_source"),
        CheckConstraint("good_quantity >= 0 AND scrap_quantity >= 0 AND rework_quantity >= 0 AND good_quantity + scrap_quantity + rework_quantity BETWEEN 1 AND 9007199254740991", name="ck_qc_inspection_quantities"),
        CheckConstraint("(rework_quantity > 0) = (repair_department_code IS NOT NULL)", name="ck_qc_inspection_repair"),
        CheckConstraint("repair_department_code IS NULL OR repair_department_code <> 'qc'", name="ck_qc_repair_department"),
        CheckConstraint("(scrap_quantity = 0 AND rework_quantity = 0) OR note ~ '[^[:space:]]'", name="ck_qc_inspection_note"),
        Index("idx_qc_inspection_order", "work_order_id", "id"),
        Index("idx_qc_inspection_repair", "repair_department_code", "id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("department_work_order.id"), nullable=False)
    source_ticket_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("department_handoff_ticket.id"), nullable=True)
    source_return_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("qc_rework_event.id", name="fk_qc_inspection_return", use_alter=True), nullable=True)
    source_pick_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse_pick.id", name="fk_qc_inspection_pick", use_alter=True), nullable=True)
    good_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scrap_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rework_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    repair_department_code: Mapped[str | None] = mapped_column(Text, ForeignKey("production_department.code"), nullable=True)
    repair_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_worker_name: Mapped[str] = mapped_column(Text, nullable=False, default='', server_default=text("''"))
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class QcReworkTicket(Base):
    __tablename__ = "qc_rework_ticket"
    __table_args__ = (UniqueConstraint("inspection_id", name="uq_qc_rework_inspection"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("qc_inspection.id"), nullable=False)


class QcReworkEvent(Base):
    __tablename__ = "qc_rework_event"
    __table_args__ = (
        Index("uq_qc_rework_event_action", "ticket_id", "action", unique=True, postgresql_where=text("revoked_at IS NULL")),
        UniqueConstraint("request_id", name="uq_qc_rework_event_request"),
        CheckConstraint("action IN ('receive', 'return')", name="ck_qc_rework_event_action"),
        CheckConstraint("quantity > 0 AND quantity <= 9007199254740991", name="ck_qc_rework_event_quantity"),
        CheckConstraint("repaired_quantity >= 0 AND unrepaired_quantity >= 0 AND ((action = 'receive' AND repaired_quantity = 0 AND unrepaired_quantity = 0) OR (action = 'return' AND repaired_quantity + unrepaired_quantity = quantity))", name="ck_qc_rework_event_result"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("qc_rework_ticket.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    repaired_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unrepaired_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class WarehouseLot(Base):
    __tablename__ = 'warehouse_lot'
    __table_args__ = (
        UniqueConstraint('receipt_movement_id', name='uq_warehouse_lot_receipt'),
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_warehouse_lot_quantity'),
        Index('idx_warehouse_lot_pool', 'product_id', 'material_key', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order.id'), nullable=False)
    receipt_movement_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order_movement.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product.id'), nullable=False)
    material_key: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class WarehousePick(Base):
    __tablename__ = 'warehouse_pick'
    __table_args__ = (
        UniqueConstraint('request_id', name='uq_warehouse_pick_request'),
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_warehouse_pick_quantity'),
        Index('idx_warehouse_pick_target', 'target_order_id', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order.id'), nullable=False)
    route_warehouse_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_work_order.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product.id'), nullable=False)
    material_key: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class WarehouseAllocation(Base):
    __tablename__ = 'warehouse_allocation'
    __table_args__ = (
        CheckConstraint('quantity > 0 AND quantity <= 9007199254740991', name='ck_warehouse_allocation_quantity'),
        Index('idx_warehouse_allocation_lot', 'lot_id'),
    )
    pick_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('warehouse_pick.id'), primary_key=True)
    lot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('warehouse_lot.id'), primary_key=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
