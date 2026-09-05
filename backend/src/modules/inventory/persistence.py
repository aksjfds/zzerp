from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


class WarehouseStock(Base):
    """Temporary warehouse row matching the future SQL Server business columns."""

    __tablename__ = "warehouse_stock"
    __table_args__ = (
        CheckConstraint("product_version > 0", name="ck_warehouse_stock_version"),
        CheckConstraint(
            "item_type IN ('part', 'assembly')",
            name="ck_warehouse_stock_item_type",
        ),
        CheckConstraint(
            "item_code = btrim(item_code) AND item_code <> ''",
            name="ck_warehouse_stock_item_code",
        ),
        CheckConstraint(
            "item_name = btrim(item_name) AND item_name <> ''",
            name="ck_warehouse_stock_item_name",
        ),
        CheckConstraint(
            "completion_status = btrim(completion_status) AND completion_status <> ''",
            name="ck_warehouse_stock_completion_status",
        ),
        CheckConstraint("inventory_unit = 'PCS'", name="ck_warehouse_stock_unit"),
        CheckConstraint(
            "(warehouse_code = 'C01' AND warehouse_name = '主料仓') OR "
            "(warehouse_code = 'C02' AND warehouse_name = '辅料仓')",
            name="ck_warehouse_stock_location",
        ),
        CheckConstraint("quantity >= 0", name="ck_warehouse_stock_quantity"),
        UniqueConstraint(
            "item_code",
            "product_version",
            "item_type",
            "completion_status",
            "warehouse_code",
            name="uq_warehouse_stock_identity",
        ),
        UniqueConstraint(
            "id",
            "item_code",
            "product_version",
            "item_type",
            "completion_status",
            "warehouse_code",
            name="uq_warehouse_stock_context",
        ),
        Index(
            "idx_warehouse_stock_allocation",
            "item_code",
            "product_version",
            "item_type",
            "warehouse_code",
            "completion_status",
            "last_inbound_date",
            "id",
            postgresql_where=text("quantity > 0"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    specification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inventory_unit: Mapped[str] = mapped_column(Text, nullable=False, default="PCS")
    warehouse_code: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_status: Mapped[str] = mapped_column(Text, nullable=False)
    last_inbound_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_outbound_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class WarehouseOperation(Base):
    """Local idempotency and audit record for operations initiated by this project."""

    __tablename__ = "warehouse_operation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["production_plan_item_id", "production_plan_id"],
            ["production_plan_item.id", "production_plan_item.production_plan_id"],
            name="fk_warehouse_operation_plan_item",
        ),
        UniqueConstraint(
            "reversal_of_operation_id",
            name="uq_warehouse_operation_reversal",
        ),
        ForeignKeyConstraint(
            ["work_order_batch_id", "work_order_id"],
            ["work_order_batch.id", "work_order_batch.work_order_id"],
            name="fk_warehouse_operation_batch_order",
        ),
        ForeignKeyConstraint(
            [
                "warehouse_stock_id",
                "item_code",
                "product_version",
                "item_type",
                "completion_status",
                "warehouse_code",
            ],
            [
                "warehouse_stock.id",
                "warehouse_stock.item_code",
                "warehouse_stock.product_version",
                "warehouse_stock.item_type",
                "warehouse_stock.completion_status",
                "warehouse_stock.warehouse_code",
            ],
            name="fk_warehouse_operation_stock_context",
        ),
        CheckConstraint(
            "operation_type IN ('inbound', 'outbound')",
            name="ck_warehouse_operation_type",
        ),
        CheckConstraint(
            "source_type IN ('plan_confirmation', 'qc_inventory', 'production_position', 'reversal')",
            name="ck_warehouse_operation_source_type",
        ),
        CheckConstraint(
            "(source_type = 'plan_confirmation' AND operation_type = 'outbound') OR "
            "(source_type IN ('qc_inventory', 'production_position') "
            "AND operation_type = 'inbound') OR source_type = 'reversal'",
            name="ck_warehouse_operation_direction",
        ),
        CheckConstraint(
            "(source_type = 'plan_confirmation' "
            "AND production_plan_id IS NOT NULL AND production_plan_item_id IS NOT NULL "
            "AND work_order_id IS NULL AND work_order_batch_id IS NULL "
            "AND production_item_id IS NULL) OR "
            "(source_type = 'qc_inventory' "
            "AND work_order_id IS NOT NULL AND work_order_batch_id IS NOT NULL "
            "AND production_item_id IS NOT NULL "
            "AND production_plan_id IS NULL AND production_plan_item_id IS NULL) OR "
            "(source_type = 'production_position' AND production_item_id IS NOT NULL "
            "AND production_plan_id IS NULL AND production_plan_item_id IS NULL "
            "AND work_order_id IS NULL AND work_order_batch_id IS NULL) OR "
            "(source_type = 'reversal' AND reversal_of_operation_id IS NOT NULL "
            "AND production_plan_id IS NULL AND production_plan_item_id IS NULL "
            "AND work_order_id IS NULL AND work_order_batch_id IS NULL "
            "AND production_item_id IS NULL)",
            name="ck_warehouse_operation_source_context",
        ),
        CheckConstraint(
            "operation_group_no = btrim(operation_group_no) "
            "AND operation_group_no <> ''",
            name="ck_warehouse_operation_group_no",
        ),
        CheckConstraint(
            "operation_no = btrim(operation_no) AND operation_no <> ''",
            name="ck_warehouse_operation_no",
        ),
        CheckConstraint(
            "left(operation_no, length(operation_group_no) + 1) "
            "= operation_group_no || ':'",
            name="ck_warehouse_operation_number_scope",
        ),
        CheckConstraint(
            "item_code = btrim(item_code) AND item_code <> ''",
            name="ck_warehouse_operation_item_code",
        ),
        CheckConstraint(
            "item_name = btrim(item_name) AND item_name <> ''",
            name="ck_warehouse_operation_item_name",
        ),
        CheckConstraint(
            "completion_status = btrim(completion_status) AND completion_status <> ''",
            name="ck_warehouse_operation_completion_status",
        ),
        CheckConstraint(
            "actor_username = btrim(actor_username) AND actor_username <> ''",
            name="ck_warehouse_operation_actor",
        ),
        CheckConstraint(
            "item_type IN ('part', 'assembly')",
            name="ck_warehouse_operation_item_type",
        ),
        CheckConstraint("inventory_unit = 'PCS'", name="ck_warehouse_operation_unit"),
        CheckConstraint(
            "(warehouse_code = 'C01' AND warehouse_name = '主料仓') OR "
            "(warehouse_code = 'C02' AND warehouse_name = '辅料仓')",
            name="ck_warehouse_operation_location",
        ),
        CheckConstraint("product_version > 0", name="ck_warehouse_operation_version"),
        CheckConstraint("quantity > 0", name="ck_warehouse_operation_quantity"),
        CheckConstraint(
            "quantity_before IS NULL OR quantity_before >= 0",
            name="ck_warehouse_operation_before",
        ),
        CheckConstraint(
            "quantity_after IS NULL OR quantity_after >= 0",
            name="ck_warehouse_operation_after",
        ),
        CheckConstraint(
            "(quantity_before IS NULL) = (quantity_after IS NULL)",
            name="ck_warehouse_operation_quantity_pair",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'uncertain')",
            name="ck_warehouse_operation_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND executed_at IS NULL "
            "AND quantity_before IS NULL AND quantity_after IS NULL AND error_message IS NULL) OR "
            "(status = 'succeeded' AND executed_at IS NOT NULL "
            "AND quantity_before IS NOT NULL AND quantity_after IS NOT NULL "
            "AND error_message IS NULL) OR "
            "(status IN ('failed', 'uncertain') AND executed_at IS NOT NULL "
            "AND error_message IS NOT NULL AND btrim(error_message) <> '')",
            name="ck_warehouse_operation_lifecycle",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR "
            "(operation_type = 'inbound' AND quantity_after = quantity_before + quantity) OR "
            "(operation_type = 'outbound' AND quantity_after = quantity_before - quantity)",
            name="ck_warehouse_operation_balance",
        ),
        CheckConstraint(
            "(manual_reviewed_at IS NULL AND manual_reviewed_by IS NULL "
            "AND manual_review_note IS NULL) OR "
            "(status = 'uncertain' AND manual_reviewed_at IS NOT NULL "
            "AND manual_reviewed_by IS NOT NULL AND manual_review_note IS NOT NULL "
            "AND btrim(manual_review_note) <> '')",
            name="ck_warehouse_operation_manual_review",
        ),
        UniqueConstraint("operation_no", name="uq_warehouse_operation_no"),
        Index("idx_warehouse_operation_group", "operation_group_no", "id"),
        Index("idx_warehouse_operation_recent", "created_at", "id"),
        Index("idx_warehouse_operation_status", "status", "created_at", "id"),
        Index(
            "idx_warehouse_operation_plan",
            "production_plan_id",
            "production_plan_item_id",
            "id",
        ),
        Index("idx_warehouse_operation_work_order", "work_order_id", "work_order_batch_id"),
        Index("idx_warehouse_operation_production_item", "production_item_id", "id"),
        Index("idx_warehouse_operation_processing_state", "processing_state_id", "id"),
        Index("idx_warehouse_operation_stock", "warehouse_stock_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation_group_no: Mapped[str] = mapped_column(Text, nullable=False)
    operation_no: Mapped[str] = mapped_column(Text, nullable=False)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    production_plan_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("production_plan.id", name="fk_warehouse_operation_plan"),
        nullable=True,
    )
    production_plan_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id", name="fk_warehouse_operation_work_order"),
        nullable=True,
    )
    work_order_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    production_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("production_item.id", name="fk_warehouse_operation_production_item"),
        nullable=True,
    )
    processing_state_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_processing_state.id", name="fk_warehouse_operation_processing_state"),
        nullable=False,
    )
    reversal_of_operation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("warehouse_operation.id", name="fk_warehouse_operation_reversal"),
        nullable=True,
    )
    warehouse_stock_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    item_code: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    specification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inventory_unit: Mapped[str] = mapped_column(Text, nullable=False, default="PCS")
    warehouse_code: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_name: Mapped[str] = mapped_column(Text, nullable=False)
    completion_status: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    actor_username: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    manual_reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    manual_reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinishedReceipt(Base):
    __tablename__ = "finished_receipt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_finished_receipt_product_version",
        ),
        UniqueConstraint(
            "replacement_for_receipt_id",
            name="uq_finished_receipt_replacement",
        ),
        CheckConstraint(
            "(work_order_batch_id IS NOT NULL AND work_order_id IS NULL) OR "
            "(work_order_batch_id IS NULL AND work_order_id IS NOT NULL)",
            name="ck_finished_receipt_source",
        ),
        CheckConstraint("product_version > 0", name="ck_finished_receipt_version"),
        CheckConstraint("quantity > 0", name="ck_finished_receipt_quantity"),
        CheckConstraint(
            "status IN ('pending', 'received', 'cancelled', 'reversed')",
            name="ck_finished_receipt_status",
        ),
        CheckConstraint("revision > 0", name="ck_finished_receipt_revision"),
        CheckConstraint(
            "(status = 'pending' AND received_at IS NULL AND received_by IS NULL "
            "AND corrected_at IS NULL AND corrected_by IS NULL) OR "
            "(status = 'received' AND received_at IS NOT NULL "
            "AND received_by IS NOT NULL AND received_by = btrim(received_by) "
            "AND received_by <> '' AND corrected_at IS NULL AND corrected_by IS NULL) OR "
            "(status = 'cancelled' AND received_at IS NULL AND received_by IS NULL "
            "AND corrected_at IS NOT NULL AND corrected_by IS NOT NULL "
            "AND corrected_by = btrim(corrected_by) AND corrected_by <> '') OR "
            "(status = 'reversed' AND received_at IS NOT NULL AND received_by IS NOT NULL "
            "AND corrected_at IS NOT NULL AND corrected_by IS NOT NULL "
            "AND corrected_by = btrim(corrected_by) AND corrected_by <> '')",
            name="ck_finished_receipt_lifecycle",
        ),
        Index(
            "idx_finished_receipt_pending",
            "status",
            "created_at",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "uq_finished_receipt_active_qc_batch",
            "work_order_batch_id",
            unique=True,
            postgresql_where=text(
                "work_order_batch_id IS NOT NULL AND status IN ('pending', 'received')"
            ),
        ),
        Index(
            "uq_finished_receipt_active_packaging_order",
            "work_order_id",
            unique=True,
            postgresql_where=text(
                "work_order_id IS NOT NULL AND status IN ('pending', 'received')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("work_order_batch.id", name="fk_finished_receipt_qc_batch"),
        nullable=True,
    )
    work_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id", name="fk_finished_receipt_packaging_order"),
        nullable=True,
    )
    replacement_for_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("finished_receipt.id", name="fk_finished_receipt_replacement"),
        nullable=True,
    )
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    received_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    received_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    corrected_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

class FinishedStock(Base):
    __tablename__ = "finished_stock"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "product_version"],
            ["product_version.product_id", "product_version.version"],
            name="fk_finished_stock_product_version",
        ),
        UniqueConstraint(
            "product_id",
            "product_version",
            name="uq_finished_stock_identity",
        ),
        CheckConstraint("product_version > 0", name="ck_finished_stock_version"),
        CheckConstraint("quantity >= 0", name="ck_finished_stock_quantity"),
        CheckConstraint("reserved_quantity >= 0", name="ck_finished_stock_reserved"),
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="ck_finished_stock_availability",
        ),
        CheckConstraint("revision > 0", name="ck_finished_stock_revision"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class FinishedStockReservation(Base):
    __tablename__ = "finished_stock_reservation"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "production_plan_item_id",
                "production_plan_id",
                "customer_order_item_id",
            ],
            [
                "production_plan_item.id",
                "production_plan_item.production_plan_id",
                "production_plan_item.customer_order_item_id",
            ],
            name="fk_finished_stock_reservation_plan_item",
        ),
        UniqueConstraint(
            "id",
            "finished_stock_id",
            "customer_order_item_id",
            name="uq_finished_stock_reservation_context",
        ),
        CheckConstraint(
            "reserved_quantity > 0",
            name="ck_finished_stock_reservation_reserved",
        ),
        CheckConstraint(
            "shipped_quantity >= 0",
            name="ck_finished_stock_reservation_shipped",
        ),
        CheckConstraint(
            "released_quantity >= 0",
            name="ck_finished_stock_reservation_released",
        ),
        CheckConstraint(
            "shipped_quantity + released_quantity <= reserved_quantity",
            name="ck_finished_stock_reservation_balance",
        ),
        Index(
            "idx_finished_stock_reservation_plan",
            "production_plan_id",
            "production_plan_item_id",
            "id",
        ),
        Index(
            "idx_finished_stock_reservation_order_open",
            "customer_order_item_id",
            "id",
            postgresql_where=text(
                "shipped_quantity + released_quantity < reserved_quantity"
            ),
        ),
        Index(
            "idx_finished_stock_reservation_recent",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    finished_stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finished_stock.id"),
        nullable=False,
    )
    production_plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    production_plan_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_order_item.id"),
        nullable=False,
    )
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    shipped_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    released_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class FinishedStockTransaction(Base):
    __tablename__ = "finished_stock_transaction"
    __table_args__ = (
        UniqueConstraint(
            "reversal_of_transaction_id",
            name="uq_finished_stock_transaction_reversal",
        ),
        ForeignKeyConstraint(
            ["customer_order_item_id", "customer_order_id"],
            ["customer_order_item.id", "customer_order_item.customer_order_id"],
            name="fk_finished_stock_transaction_order_item",
        ),
        ForeignKeyConstraint(
            [
                "finished_stock_reservation_id",
                "finished_stock_id",
                "customer_order_item_id",
            ],
            [
                "finished_stock_reservation.id",
                "finished_stock_reservation.finished_stock_id",
                "finished_stock_reservation.customer_order_item_id",
            ],
            name="fk_finished_stock_transaction_reservation",
        ),
        CheckConstraint(
            "transaction_type IN ('receipt', 'receipt_reversal', "
            "'customer_shipment', 'customer_shipment_reversal')",
            name="ck_finished_stock_transaction_type",
        ),
        CheckConstraint("quantity > 0", name="ck_finished_stock_transaction_quantity"),
        CheckConstraint(
            "operation_group_no = btrim(operation_group_no) AND operation_group_no <> ''",
            name="ck_finished_stock_transaction_group",
        ),
        CheckConstraint(
            "quantity_before >= 0",
            name="ck_finished_stock_transaction_before",
        ),
        CheckConstraint(
            "quantity_after >= 0",
            name="ck_finished_stock_transaction_after",
        ),
        CheckConstraint(
            "actor_username = btrim(actor_username) AND actor_username <> ''",
            name="ck_finished_stock_transaction_actor",
        ),
        CheckConstraint(
            "(transaction_type IN ('receipt', 'receipt_reversal') "
            "AND finished_receipt_id IS NOT NULL "
            "AND customer_order_id IS NULL AND customer_order_item_id IS NULL "
            "AND finished_stock_reservation_id IS NULL) OR "
            "(transaction_type IN ('customer_shipment', 'customer_shipment_reversal') "
            "AND finished_receipt_id IS NULL "
            "AND customer_order_id IS NOT NULL AND customer_order_item_id IS NOT NULL)",
            name="ck_finished_stock_transaction_source",
        ),
        CheckConstraint(
            "(transaction_type = 'receipt' "
            "AND quantity_after = quantity_before + quantity) OR "
            "(transaction_type = 'customer_shipment' "
            "AND quantity_after = quantity_before - quantity) OR "
            "(transaction_type = 'receipt_reversal' "
            "AND quantity_after = quantity_before - quantity) OR "
            "(transaction_type = 'customer_shipment_reversal' "
            "AND quantity_after = quantity_before + quantity)",
            name="ck_finished_stock_transaction_balance",
        ),
        CheckConstraint(
            "(transaction_type IN ('receipt', 'customer_shipment') "
            "AND reversal_of_transaction_id IS NULL) OR "
            "(transaction_type IN ('receipt_reversal', 'customer_shipment_reversal') "
            "AND reversal_of_transaction_id IS NOT NULL)",
            name="ck_finished_stock_transaction_reversal",
        ),
        Index(
            "uq_finished_stock_transaction_receipt",
            "finished_receipt_id",
            unique=True,
            postgresql_where=text("transaction_type = 'receipt'"),
        ),
        Index(
            "idx_finished_stock_transaction_stock",
            "finished_stock_id",
            "created_at",
            "id",
        ),
        Index(
            "idx_finished_stock_transaction_order",
            "customer_order_item_id",
            "created_at",
            "id",
            postgresql_where=text("customer_order_item_id IS NOT NULL"),
        ),
        Index(
            "idx_finished_stock_transaction_recent",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    finished_stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finished_stock.id"),
        nullable=False,
    )
    finished_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("finished_receipt.id"),
        nullable=True,
    )
    customer_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("customer_order.id"),
        nullable=True,
    )
    customer_order_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("customer_order_item.id"),
        nullable=True,
    )
    finished_stock_reservation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    operation_group_no: Mapped[str] = mapped_column(Text, nullable=False)
    reversal_of_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "finished_stock_transaction.id",
            name="fk_finished_stock_transaction_reversal",
        ),
        nullable=True,
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
