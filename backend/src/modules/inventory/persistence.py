from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class InventoryStock(Base):
    __tablename__ = "inventory_stock"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_inventory_stock_product_version",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id", "product_version"],
            ["product_bom.id", "product_bom.product_id", "product_bom.product_version"],
            name="fk_inventory_stock_bom_version",
        ),
        CheckConstraint(
            "department_code IN ('warehouse', 'finished')",
            name="ck_inventory_stock_department",
        ),
        CheckConstraint(
            "item_type IN ('part', 'assembly', 'finished_product')",
            name="ck_inventory_stock_item_type",
        ),
        CheckConstraint(
            "(department_code = 'finished' AND item_type = 'finished_product') OR "
            "(department_code = 'warehouse' AND item_type IN ('part', 'assembly'))",
            name="ck_inventory_stock_location_type",
        ),
        CheckConstraint("product_version > 0", name="ck_inventory_stock_version"),
        CheckConstraint(
            "(item_type = 'part' AND product_bom_id IS NOT NULL) OR "
            "(item_type IN ('assembly', 'finished_product') AND product_bom_id IS NULL)",
            name="ck_inventory_stock_bom_scope",
        ),
        CheckConstraint("quantity >= 0", name="ck_inventory_stock_quantity"),
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="ck_inventory_stock_reserved_quantity",
        ),
        CheckConstraint("revision > 0", name="ck_inventory_stock_revision"),
        Index(
            "idx_inventory_stock_component",
            "product_id",
            "product_version",
            "item_type",
            "product_bom_id",
            "flow_node_id",
        ),
        Index("idx_inventory_stock_department", "department_code", "item_type"),
        Index(
            "uq_inventory_stock_part_identity",
            "department_code",
            "item_type",
            "product_id",
            "product_version",
            "product_bom_id",
            "flow_node_id",
            "completed_flow_node_id",
            unique=True,
            postgresql_where=text("item_type = 'part'"),
        ),
        Index(
            "uq_inventory_stock_node_identity",
            "department_code",
            "item_type",
            "product_id",
            "product_version",
            "flow_node_id",
            "completed_flow_node_id",
            unique=True,
            postgresql_where=text("item_type IN ('assembly', 'finished_product')"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    completed_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class InventoryReservation(Base):
    __tablename__ = "inventory_reservation"
    __table_args__ = (
        CheckConstraint("reserved_quantity > 0", name="ck_inventory_reservation_quantity"),
        CheckConstraint(
            "issued_quantity >= 0 AND issued_quantity <= reserved_quantity",
            name="ck_inventory_reservation_issued",
        ),
        UniqueConstraint(
            "id",
            "production_plan_id",
            "production_plan_item_id",
            "inventory_stock_id",
            name="uq_inventory_reservation_context",
        ),
        ForeignKeyConstraint(
            ["production_plan_item_id", "production_plan_id"],
            ["production_plan_item.id", "production_plan_item.production_plan_id"],
            name="fk_inventory_reservation_plan_item",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('reserved', 'issued', 'released')",
            name="ck_inventory_reservation_status",
        ),
        CheckConstraint(
            "(status = 'reserved' AND issued_quantity = 0 AND issued_at IS NULL "
            "AND released_at IS NULL) OR "
            "(status = 'issued' AND issued_quantity > 0 AND issued_at IS NOT NULL "
            "AND released_at IS NULL) OR "
            "(status = 'released' AND issued_quantity = 0 AND released_at IS NOT NULL)",
            name="ck_inventory_reservation_state",
        ),
        Index("idx_inventory_reservation_plan", "production_plan_id", "status"),
        Index("idx_inventory_reservation_item", "production_plan_item_id"),
        Index("idx_inventory_reservation_stock", "inventory_stock_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    production_plan_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_stock.id"), nullable=False
    )
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="reserved")
    reserved_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    issued_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    issued_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class InventoryReceipt(Base):
    __tablename__ = "inventory_receipt"
    __table_args__ = (
        CheckConstraint("product_version > 0", name="ck_inventory_receipt_version"),
        CheckConstraint("quantity > 0", name="ck_inventory_receipt_quantity"),
        CheckConstraint(
            "department_code IN ('warehouse', 'finished')",
            name="ck_inventory_receipt_department",
        ),
        CheckConstraint(
            "(source_customer_order_id IS NULL AND source_customer_order_item_id IS NULL "
            "AND source_production_item_id IS NULL) OR "
            "(source_customer_order_id IS NOT NULL AND source_customer_order_item_id IS NOT NULL "
            "AND source_production_item_id IS NOT NULL)",
            name="ck_inventory_receipt_source_context",
        ),
        ForeignKeyConstraint(
            [
                "source_customer_order_item_id",
                "source_customer_order_id",
                "product_id",
                "product_version",
            ],
            [
                "customer_order_item.id",
                "customer_order_item.customer_order_id",
                "customer_order_item.product_id",
                "customer_order_item.product_version",
            ],
            name="fk_inventory_receipt_order_context",
        ),
        ForeignKeyConstraint(
            [
                "source_production_item_id",
                "source_customer_order_item_id",
                "product_id",
                "product_version",
            ],
            [
                "production_item.id",
                "production_item.customer_order_item_id",
                "production_item.product_id",
                "production_item.product_version",
            ],
            name="fk_inventory_receipt_production_context",
        ),
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_inventory_receipt_product_version",
        ),
        ForeignKeyConstraint(
            ["product_bom_id", "product_id", "product_version"],
            ["product_bom.id", "product_bom.product_id", "product_bom.product_version"],
            name="fk_inventory_receipt_bom_version",
        ),
        CheckConstraint(
            "(item_type = 'part' AND product_bom_id IS NOT NULL) OR "
            "(item_type IN ('assembly', 'finished_product') AND product_bom_id IS NULL)",
            name="ck_inventory_receipt_bom_scope",
        ),
        CheckConstraint(
            "item_type IN ('part', 'assembly', 'finished_product')",
            name="ck_inventory_receipt_item_type",
        ),
        CheckConstraint(
            "(department_code = 'finished' AND item_type = 'finished_product') OR "
            "(department_code = 'warehouse' AND item_type IN ('part', 'assembly'))",
            name="ck_inventory_receipt_location_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled')",
            name="ck_inventory_receipt_status",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL) "
            "OR (status <> 'confirmed' AND confirmed_at IS NULL AND confirmed_by IS NULL)",
            name="ck_inventory_receipt_confirmation",
        ),
        Index("idx_inventory_receipt_status", "department_code", "status", "id"),
        Index("idx_inventory_receipt_order_item", "source_customer_order_item_id", "id"),
        Index("idx_inventory_receipt_production_item", "source_production_item_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_customer_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_customer_order_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_production_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    department_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_bom_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    completed_flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transaction"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inventory_transaction_quantity"),
        CheckConstraint(
            "transaction_type IN ('receipt', 'reserve', 'release', 'issue', "
            "'adjust_in', 'adjust_out')",
            name="ck_inventory_transaction_type",
        ),
        CheckConstraint(
            "(transaction_type = 'receipt' AND inventory_receipt_id IS NOT NULL "
            "AND inventory_reservation_id IS NULL AND production_plan_id IS NULL "
            "AND production_plan_item_id IS NULL) OR "
            "(transaction_type IN ('reserve', 'release', 'issue') "
            "AND inventory_receipt_id IS NULL AND inventory_reservation_id IS NOT NULL "
            "AND production_plan_id IS NOT NULL AND production_plan_item_id IS NOT NULL) OR "
            "(transaction_type IN ('adjust_in', 'adjust_out') "
            "AND inventory_receipt_id IS NULL AND inventory_reservation_id IS NULL "
            "AND production_plan_id IS NULL AND production_plan_item_id IS NULL)",
            name="ck_inventory_transaction_source",
        ),
        ForeignKeyConstraint(
            ["production_plan_item_id", "production_plan_id"],
            ["production_plan_item.id", "production_plan_item.production_plan_id"],
            name="fk_inventory_transaction_plan_item",
        ),
        ForeignKeyConstraint(
            [
                "inventory_reservation_id",
                "production_plan_id",
                "production_plan_item_id",
                "inventory_stock_id",
            ],
            [
                "inventory_reservation.id",
                "inventory_reservation.production_plan_id",
                "inventory_reservation.production_plan_item_id",
                "inventory_reservation.inventory_stock_id",
            ],
            name="fk_inventory_transaction_reservation_context",
        ),
        CheckConstraint(
            "quantity_before >= 0",
            name="ck_inventory_transaction_quantity_before",
        ),
        CheckConstraint(
            "quantity_after >= 0",
            name="ck_inventory_transaction_quantity_after",
        ),
        CheckConstraint(
            "reserved_before >= 0",
            name="ck_inventory_transaction_reserved_before",
        ),
        CheckConstraint(
            "reserved_after >= 0",
            name="ck_inventory_transaction_reserved_after",
        ),
        Index("idx_inventory_transaction_stock", "inventory_stock_id", "id"),
        Index("idx_inventory_transaction_plan", "production_plan_id", "id"),
        Index("idx_inventory_transaction_reservation", "inventory_reservation_id", "id"),
        Index("idx_inventory_transaction_receipt", "inventory_receipt_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inventory_stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_stock.id"), nullable=False
    )
    production_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("production_plan.id"), nullable=True
    )
    production_plan_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inventory_reservation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inventory_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory_receipt.id"), nullable=True
    )
    transaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_before: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_after: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_username: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class FinishedOrderStock(Base):
    __tablename__ = "finished_order_stock"
    __table_args__ = (
        CheckConstraint("product_version > 0", name="ck_finished_order_stock_version"),
        CheckConstraint("unit_quantity > 0", name="ck_finished_order_stock_unit"),
        CheckConstraint("pending_quantity >= 0", name="ck_finished_order_stock_pending"),
        CheckConstraint("available_quantity >= 0", name="ck_finished_order_stock_available"),
        CheckConstraint("shipped_quantity >= 0", name="ck_finished_order_stock_shipped"),
        CheckConstraint("transferred_quantity >= 0", name="ck_finished_order_stock_transferred"),
        CheckConstraint("revision > 0", name="ck_finished_order_stock_revision"),
        UniqueConstraint(
            "production_item_id",
            "flow_node_id",
            name="uq_finished_order_stock_item_node",
        ),
        Index("idx_finished_order_stock_order", "customer_order_id", "id"),
        Index("idx_finished_order_stock_order_item", "customer_order_item_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer_order.id", ondelete="CASCADE"), nullable=False
    )
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer_order_item.id", ondelete="CASCADE"), nullable=False
    )
    production_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "production_item.id",
            name="fk_finished_order_stock_production_item",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipped_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transferred_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    received_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_shipped_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_shipped_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class FinishedGoodsTransaction(Base):
    __tablename__ = "finished_goods_transaction"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_finished_goods_transaction_quantity"),
        CheckConstraint(
            "transaction_type IN ('finished_receipt', 'customer_shipment', "
            "'finished_stock_issue', 'finished_surplus_transfer')",
            name="ck_finished_goods_transaction_type",
        ),
        CheckConstraint("quantity_before >= 0", name="ck_finished_goods_transaction_before"),
        CheckConstraint("quantity_after >= 0", name="ck_finished_goods_transaction_after"),
        Index("idx_finished_goods_transaction_lot", "finished_order_stock_id", "id"),
        Index("idx_finished_goods_transaction_created", text("created_at DESC"), text("id DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    finished_order_stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finished_order_stock.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_username: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
