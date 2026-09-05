"""QC- or packaging-created finished receipts and whole-batch stock receiving."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.time import utc_now
from modules.engineering.model_api import Product
from modules.errors import DomainError
from modules.inventory.persistence import (
    FinishedReceipt,
    FinishedStock,
    FinishedStockTransaction,
)
from modules.production_core.operational_api import (
    load_product_flow,
    terminal_unit_quantity,
)


def register_pending_finished_receipt(
    session: Session,
    *,
    work_order_batch_id: int,
    product_id: int,
    product_version: int,
    inbound_node_id: str,
    released_quantity: int,
) -> FinishedReceipt:
    """Create the one pending receipt represented by a QC release batch."""
    return _register_pending_finished_receipt(
        session,
        work_order_batch_id=work_order_batch_id,
        work_order_id=None,
        product_id=product_id,
        product_version=product_version,
        inbound_node_id=inbound_node_id,
        released_quantity=released_quantity,
    )


def register_pending_packaging_receipt(
    session: Session,
    *,
    work_order_id: int,
    product_id: int,
    product_version: int,
    inbound_node_id: str,
    released_quantity: int,
) -> FinishedReceipt:
    """Create the one pending receipt represented by a completed packaging order."""
    return _register_pending_finished_receipt(
        session,
        work_order_batch_id=None,
        work_order_id=work_order_id,
        product_id=product_id,
        product_version=product_version,
        inbound_node_id=inbound_node_id,
        released_quantity=released_quantity,
    )


def _register_pending_finished_receipt(
    session: Session,
    *,
    work_order_batch_id: int | None,
    work_order_id: int | None,
    product_id: int,
    product_version: int,
    inbound_node_id: str,
    released_quantity: int,
) -> FinishedReceipt:
    if released_quantity <= 0:
        raise DomainError("finished_receipt_quantity_invalid", "成品待入库数量必须大于0")
    if (work_order_batch_id is None) == (work_order_id is None):
        raise DomainError("finished_receipt_source_invalid", "成品待入库来源必须且只能有一个")

    flow, nodes = load_product_flow(session, product_id, product_version)
    inbound_node = nodes.get(inbound_node_id)
    if inbound_node is None or inbound_node.get("type") != "finished_inbound":
        raise DomainError("finished_receipt_context_invalid", "成品入库节点资料不完整", status_code=409)
    unit_quantity = terminal_unit_quantity(session, flow, nodes, inbound_node_id)
    if unit_quantity is None:
        raise DomainError("finished_receipt_unit_invalid", "无法确定成品计量单位", status_code=409)
    if released_quantity % unit_quantity:
        raise DomainError(
            "finished_receipt_unit_incomplete",
            f"待入库物料数量必须是每件产品用量 {unit_quantity} 的整数倍",
        )
    quantity = released_quantity // unit_quantity

    source_condition = (
        FinishedReceipt.work_order_batch_id == work_order_batch_id
        if work_order_batch_id is not None
        else FinishedReceipt.work_order_id == work_order_id
    )
    existing = session.scalar(
        select(FinishedReceipt)
        .where(source_condition, FinishedReceipt.status.in_(("pending", "received")))
        .with_for_update()
    )
    if existing is not None:
        if (
            existing.work_order_batch_id != work_order_batch_id
            or existing.work_order_id != work_order_id
            or existing.product_id != product_id
            or existing.product_version != product_version
            or existing.quantity != quantity
        ):
            raise DomainError(
                "finished_receipt_source_conflict",
                "该来源的成品待入库资料不一致",
                status_code=409,
            )
        return existing

    receipt = FinishedReceipt(
        work_order_batch_id=work_order_batch_id,
        work_order_id=work_order_id,
        product_id=product_id,
        product_version=product_version,
        quantity=quantity,
    )
    session.add(receipt)
    session.flush()
    return receipt


def list_finished_receipts() -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(FinishedReceipt, Product)
            .join(Product, Product.id == FinishedReceipt.product_id)
            .where(FinishedReceipt.status == "pending")
            .order_by(
                FinishedReceipt.created_at,
                FinishedReceipt.id,
            )
        )
        return [_serialize_receipt(receipt, product) for receipt, product in rows]


def confirm_finished_receipt(receipt_id: int, actor_username: str) -> dict:
    actor = actor_username.strip()
    if not actor:
        raise DomainError("finished_receipt_actor_invalid", "入库操作人不能为空")

    with SessionLocal.begin() as session:
        receipt = session.scalar(
            select(FinishedReceipt)
            .where(FinishedReceipt.id == receipt_id)
            .with_for_update()
        )
        if receipt is None:
            raise DomainError("finished_receipt_not_found", "待入库批次不存在", status_code=404)
        if receipt.status != "pending":
            raise DomainError("finished_receipt_already_received", "该批次已经完成入库", status_code=409)

        received_at = utc_now()
        stock = session.execute(
            insert(FinishedStock)
            .values(
                product_id=receipt.product_id,
                product_version=receipt.product_version,
                quantity=receipt.quantity,
                reserved_quantity=0,
                revision=1,
                updated_at=received_at,
            )
            .on_conflict_do_update(
                constraint="uq_finished_stock_identity",
                set_={
                    "quantity": FinishedStock.quantity + receipt.quantity,
                    "revision": FinishedStock.revision + 1,
                    "updated_at": received_at,
                },
            )
            .returning(FinishedStock)
        ).scalar_one()
        quantity_before = stock.quantity - receipt.quantity

        receipt.status = "received"
        receipt.received_at = received_at
        receipt.received_by = actor
        receipt.revision += 1
        session.add(
            FinishedStockTransaction(
                finished_stock_id=stock.id,
                finished_receipt_id=receipt.id,
                operation_group_no=f"receipt:{receipt.id}",
                reversal_of_transaction_id=None,
                transaction_type="receipt",
                quantity=receipt.quantity,
                quantity_before=quantity_before,
                quantity_after=stock.quantity,
                actor_username=actor,
                reason="成品整批入库",
            )
        )
        session.flush()

        product = session.get(Product, receipt.product_id)
        if product is None:
            raise DomainError("finished_receipt_product_missing", "待入库批次的产品不存在", status_code=409)
        return _serialize_receipt(receipt, product)


def cancel_pending_finished_receipt(
    session: Session,
    *,
    receipt: FinishedReceipt,
    actor_username: str,
    reason: str,
) -> None:
    if receipt.status != "pending":
        raise DomainError(
            "finished_receipt_already_received",
            "成品已经确认入库，不能撤回上游操作",
            status_code=409,
        )
    receipt.status = "cancelled"
    receipt.corrected_at = utc_now()
    receipt.corrected_by = actor_username
    receipt.correction_reason = reason
    receipt.revision += 1


def cancel_pending_packaging_receipt(
    session: Session,
    *,
    work_order_id: int,
    actor_username: str,
) -> None:
    receipt = session.scalar(
        select(FinishedReceipt)
        .where(FinishedReceipt.work_order_id == work_order_id)
        .where(FinishedReceipt.status == "pending")
        .with_for_update()
    )
    if receipt is None:
        return
    cancel_pending_finished_receipt(
        session,
        receipt=receipt,
        actor_username=actor_username,
        reason="撤回装包工单结果",
    )


def cancel_pending_qc_receipt(
    session: Session,
    *,
    work_order_batch_id: int,
    actor_username: str,
) -> None:
    receipt = session.scalar(
        select(FinishedReceipt)
        .where(FinishedReceipt.work_order_batch_id == work_order_batch_id)
        .where(FinishedReceipt.status == "pending")
        .with_for_update()
    )
    if receipt is None:
        return
    cancel_pending_finished_receipt(
        session,
        receipt=receipt,
        actor_username=actor_username,
        reason="撤回 QC 放行",
    )


def reverse_finished_receipt(
    receipt_id: int,
    actor_username: str,
    reason: str | None = None,
) -> dict:
    actor = actor_username.strip()
    if not actor:
        raise DomainError("finished_receipt_actor_invalid", "入库操作人不能为空")
    with SessionLocal.begin() as session:
        receipt = session.get(FinishedReceipt, receipt_id, with_for_update=True)
        if receipt is None:
            raise DomainError("finished_receipt_not_found", "成品入库记录不存在", status_code=404)
        if receipt.status != "received":
            raise DomainError("finished_receipt_not_reversible", "只有已入库批次可以冲销", status_code=409)
        original = session.scalar(
            select(FinishedStockTransaction)
            .where(
                FinishedStockTransaction.finished_receipt_id == receipt.id,
                FinishedStockTransaction.transaction_type == "receipt",
            )
            .with_for_update()
        )
        if original is None:
            raise DomainError("finished_receipt_transaction_missing", "成品入库流水不存在", status_code=409)
        if session.scalar(select(FinishedStockTransaction.id).where(
            FinishedStockTransaction.reversal_of_transaction_id == original.id
        )) is not None:
            raise DomainError("finished_receipt_already_reversed", "该批入库已经冲销", status_code=409)
        stock = session.get(FinishedStock, original.finished_stock_id, with_for_update=True)
        if stock is None or stock.quantity - stock.reserved_quantity < receipt.quantity:
            raise DomainError(
                "finished_receipt_stock_used",
                "该批入库对应的可用成品已被占用或发货，不能冲销",
                status_code=409,
            )
        quantity_before = stock.quantity
        stock.quantity -= receipt.quantity
        stock.revision += 1
        stock.updated_at = utc_now()
        receipt.status = "reversed"
        receipt.corrected_at = utc_now()
        receipt.corrected_by = actor
        receipt.correction_reason = (reason or "").strip() or "成品入库冲销"
        receipt.revision += 1
        session.flush([receipt])
        session.add(FinishedReceipt(
            work_order_batch_id=receipt.work_order_batch_id,
            work_order_id=receipt.work_order_id,
            replacement_for_receipt_id=receipt.id,
            product_id=receipt.product_id,
            product_version=receipt.product_version,
            quantity=receipt.quantity,
            status="pending",
        ))
        session.add(FinishedStockTransaction(
            finished_stock_id=stock.id,
            finished_receipt_id=receipt.id,
            operation_group_no=f"receipt-reversal:{receipt.id}",
            reversal_of_transaction_id=original.id,
            transaction_type="receipt_reversal",
            quantity=receipt.quantity,
            quantity_before=quantity_before,
            quantity_after=stock.quantity,
            actor_username=actor,
            reason=receipt.correction_reason,
        ))
        session.flush()
        product = session.get(Product, receipt.product_id)
        if product is None:
            raise DomainError("finished_receipt_product_missing", "入库批次的产品不存在", status_code=409)
        return _serialize_receipt(receipt, product)


def _serialize_receipt(receipt: FinishedReceipt, product: Product) -> dict:
    return {
        "id": receipt.id,
        "work_order_batch_id": receipt.work_order_batch_id,
        "work_order_id": receipt.work_order_id,
        "product_id": receipt.product_id,
        "product_version": receipt.product_version,
        "item_code": product.factory_code,
        "item_name": product.product_name,
        "quantity": receipt.quantity,
        "status": receipt.status,
        "received_at": receipt.received_at,
        "received_by": receipt.received_by,
        "corrected_at": receipt.corrected_at,
        "corrected_by": receipt.corrected_by,
        "correction_reason": receipt.correction_reason,
        "created_at": receipt.created_at,
        "revision": receipt.revision,
    }


__all__ = [
    "confirm_finished_receipt",
    "cancel_pending_finished_receipt",
    "cancel_pending_packaging_receipt",
    "cancel_pending_qc_receipt",
    "list_finished_receipts",
    "register_pending_packaging_receipt",
    "register_pending_finished_receipt",
    "reverse_finished_receipt",
]
