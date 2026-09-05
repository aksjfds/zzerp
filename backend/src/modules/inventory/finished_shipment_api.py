"""Customer shipment operations backed by the unified finished stock."""

from collections.abc import Collection
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.time import utc_now
from modules.engineering.model_api import Product
from modules.errors import DomainError
from modules.inventory.persistence import (
    FinishedStock,
    FinishedStockReservation,
    FinishedStockTransaction,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.sales.transaction_api import close_fully_shipped_order
from modules.sales.transaction_api import reopen_order_after_shipment_reversal


def list_finished_shipment_candidates() -> list[dict]:
    with SessionLocal() as session:
        shipped_totals = _shipped_totals_subquery()
        reserved_totals = _open_reservation_totals_subquery()
        statement = (
            select(
                CustomerOrderItem,
                CustomerOrder,
                Product,
                FinishedStock,
                func.coalesce(shipped_totals.c.quantity, 0),
                func.coalesce(reserved_totals.c.quantity, 0),
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == CustomerOrderItem.customer_order_id,
            )
            .join(Product, Product.id == CustomerOrderItem.product_id)
            .outerjoin(
                FinishedStock,
                (FinishedStock.product_id == CustomerOrderItem.product_id)
                & (FinishedStock.product_version == CustomerOrderItem.product_version),
            )
            .outerjoin(
                shipped_totals,
                shipped_totals.c.customer_order_item_id == CustomerOrderItem.id,
            )
            .outerjoin(
                reserved_totals,
                reserved_totals.c.customer_order_item_id == CustomerOrderItem.id,
            )
            .where(CustomerOrder.status == "planned")
            .order_by(CustomerOrder.id, CustomerOrderItem.id)
        )
        return [
            _serialize_candidate(order_item, order, product, stock, shipped, reserved)
            for order_item, order, product, stock, shipped, reserved
            in session.execute(statement)
        ]


def ship_finished_order_item(
    customer_order_item_id: int,
    quantity: int,
    actor_username: str,
) -> dict:
    if quantity <= 0:
        raise DomainError("finished_shipment_quantity_invalid", "发货数量必须大于0")
    actor = actor_username.strip()
    if not actor:
        raise DomainError("finished_shipment_actor_required", "发货操作人不能为空")

    with SessionLocal.begin() as session:
        customer_order_id = session.scalar(
            select(CustomerOrderItem.customer_order_id).where(
                CustomerOrderItem.id == customer_order_item_id
            )
        )
        if customer_order_id is None:
            raise DomainError(
                "customer_order_item_not_found",
                "订单产品不存在",
                status_code=404,
            )
        order = session.get(
            CustomerOrder,
            customer_order_id,
            with_for_update=True,
        )
        if order is None or order.status != "planned":
            raise DomainError(
                "customer_order_not_shippable",
                "当前订单不能发货",
                status_code=409,
            )
        order_item = session.scalar(
            select(CustomerOrderItem)
            .where(CustomerOrderItem.id == customer_order_item_id)
            .with_for_update()
        )
        if order_item is None or order_item.customer_order_id != order.id:
            raise DomainError(
                "customer_order_item_changed",
                "订单产品已发生变化，请重新加载",
                status_code=409,
            )

        shipped_quantity = _item_shipped_quantity(session, order_item.id)
        outstanding_quantity = max(order_item.quantity - shipped_quantity, 0)
        if quantity > outstanding_quantity:
            raise DomainError(
                "finished_shipment_exceeds_order",
                "发货数量不能超过订单剩余需求",
            )

        stock = session.scalar(
            select(FinishedStock)
            .where(
                FinishedStock.product_id == order_item.product_id,
                FinishedStock.product_version == order_item.product_version,
            )
            .with_for_update()
        )
        if stock is None:
            raise DomainError(
                "finished_stock_unavailable",
                "成品库存不足",
                status_code=409,
            )

        open_reservations = list(session.scalars(
            select(FinishedStockReservation)
            .where(
                FinishedStockReservation.finished_stock_id == stock.id,
                FinishedStockReservation.customer_order_item_id == order_item.id,
                FinishedStockReservation.shipped_quantity
                + FinishedStockReservation.released_quantity
                < FinishedStockReservation.reserved_quantity,
            )
            .order_by(FinishedStockReservation.id)
            .with_for_update()
        ))
        if len(open_reservations) > 1:
            raise DomainError(
                "finished_reservation_context_conflict",
                "该订单的成品库存占用记录不唯一，请检查生产计划数据",
                status_code=409,
            )
        reservation = open_reservations[0] if open_reservations else None
        reserved_for_order = _open_reservation_quantity(reservation)
        unreserved_quantity = stock.quantity - stock.reserved_quantity
        if quantity > reserved_for_order + unreserved_quantity:
            raise DomainError(
                "finished_stock_unavailable",
                "成品可发货数量不足",
                status_code=409,
            )

        reserved_shipment = min(quantity, reserved_for_order)
        if reservation is not None and reserved_shipment:
            reservation.shipped_quantity += reserved_shipment
            reservation.updated_at = utc_now()
            stock.reserved_quantity -= reserved_shipment

        quantity_before = stock.quantity
        stock.quantity -= quantity
        stock.revision += 1
        stock.updated_at = utc_now()
        direct_shipment = quantity - reserved_shipment
        operation_group_no = f"shipment:{order_item.id}:{uuid4().hex}"
        running_quantity = quantity_before
        if reserved_shipment:
            running_quantity = _record_shipment_transaction(
                session,
                stock=stock,
                order=order,
                order_item=order_item,
                reservation=reservation,
                quantity=reserved_shipment,
                quantity_before=running_quantity,
                actor_username=actor,
                operation_group_no=operation_group_no,
            )
        if direct_shipment:
            running_quantity = _record_shipment_transaction(
                session,
                stock=stock,
                order=order,
                order_item=order_item,
                reservation=None,
                quantity=direct_shipment,
                quantity_before=running_quantity,
                actor_username=actor,
                operation_group_no=operation_group_no,
            )
        if running_quantity != stock.quantity:
            raise DomainError(
                "finished_shipment_balance_invalid",
                "成品发货流水与库存变动不一致",
                status_code=409,
            )
        session.flush()

        if shipped_quantity + quantity >= order_item.quantity:
            _release_open_reservation(stock, reservation)
        if _order_is_fully_shipped(session, order.id):
            close_fully_shipped_order(session, order.id)
            session.flush()

        product = session.get(Product, order_item.product_id)
        if product is None:
            raise DomainError("product_not_found", "产品不存在", status_code=409)
        return _serialize_candidate(
            order_item,
            order,
            product,
            stock,
            _item_shipped_quantity(session, order_item.id),
            _item_open_reservation_quantity(session, order_item.id),
        )


def order_item_shipped_quantities(
    session: Session,
    customer_order_item_ids: Collection[int],
) -> dict[int, int]:
    if not customer_order_item_ids:
        return {}
    return {
        order_item_id: int(quantity)
        for order_item_id, quantity in session.execute(
            select(
                FinishedStockTransaction.customer_order_item_id,
                func.coalesce(func.sum(_shipment_signed_quantity()), 0),
            )
            .where(
                FinishedStockTransaction.customer_order_item_id.in_(
                    customer_order_item_ids
                ),
                FinishedStockTransaction.transaction_type.in_((
                    "customer_shipment", "customer_shipment_reversal"
                )),
            )
            .group_by(FinishedStockTransaction.customer_order_item_id)
        )
    }


def _record_shipment_transaction(
    session: Session,
    *,
    stock: FinishedStock,
    order: CustomerOrder,
    order_item: CustomerOrderItem,
    reservation: FinishedStockReservation | None,
    quantity: int,
    quantity_before: int,
    actor_username: str,
    operation_group_no: str,
) -> int:
    quantity_after = quantity_before - quantity
    session.add(FinishedStockTransaction(
        finished_stock_id=stock.id,
        finished_receipt_id=None,
        customer_order_id=order.id,
        customer_order_item_id=order_item.id,
        finished_stock_reservation_id=(reservation.id if reservation else None),
        operation_group_no=operation_group_no,
        reversal_of_transaction_id=None,
        transaction_type="customer_shipment",
        quantity=quantity,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        actor_username=actor_username,
        reason=f"订单 {order.customer_order_no} 发货",
    ))
    return quantity_after


def reverse_finished_shipment(
    transaction_id: int,
    actor_username: str,
    reason: str | None = None,
) -> dict:
    actor = actor_username.strip()
    if not actor:
        raise DomainError("finished_shipment_actor_required", "发货冲销操作人不能为空")
    with SessionLocal.begin() as session:
        selected = session.get(FinishedStockTransaction, transaction_id)
        if selected is None or selected.transaction_type != "customer_shipment":
            raise DomainError("finished_shipment_not_found", "发货流水不存在", status_code=404)
        originals = list(session.scalars(
            select(FinishedStockTransaction)
            .where(
                FinishedStockTransaction.operation_group_no == selected.operation_group_no,
                FinishedStockTransaction.transaction_type == "customer_shipment",
            )
            .order_by(FinishedStockTransaction.id)
            .with_for_update()
        ))
        original_ids = [item.id for item in originals]
        if session.scalar(select(FinishedStockTransaction.id).where(
            FinishedStockTransaction.reversal_of_transaction_id.in_(original_ids)
        ).limit(1)) is not None:
            raise DomainError("finished_shipment_already_reversed", "该次发货已经冲销", status_code=409)
        item_transactions = list(session.scalars(
            select(FinishedStockTransaction)
            .where(
                FinishedStockTransaction.customer_order_item_id
                == selected.customer_order_item_id,
                FinishedStockTransaction.transaction_type.in_((
                    "customer_shipment",
                    "customer_shipment_reversal",
                )),
            )
            .order_by(FinishedStockTransaction.id)
            .with_for_update()
        ))
        reversed_original_ids = {
            item.reversal_of_transaction_id
            for item in item_transactions
            if item.reversal_of_transaction_id is not None
        }
        latest_id = max(
            (
                item.id
                for item in item_transactions
                if item.transaction_type == "customer_shipment"
                and item.id not in reversed_original_ids
            ),
            default=None,
        )
        if latest_id not in original_ids:
            raise DomainError(
                "finished_shipment_not_latest",
                "请先冲销该订单产品更晚的发货记录",
                status_code=409,
            )
        stock = session.get(FinishedStock, selected.finished_stock_id, with_for_update=True)
        order = session.get(CustomerOrder, selected.customer_order_id, with_for_update=True)
        order_item = session.get(CustomerOrderItem, selected.customer_order_item_id)
        if stock is None or order is None or order_item is None:
            raise DomainError("finished_shipment_context_missing", "发货业务资料不完整", status_code=409)

        reservation_ids = {
            item.finished_stock_reservation_id
            for item in originals
            if item.finished_stock_reservation_id is not None
        }
        reservations = list(session.scalars(
            select(FinishedStockReservation)
            .where(FinishedStockReservation.id.in_(reservation_ids))
            .order_by(FinishedStockReservation.id)
            .with_for_update()
        )) if reservation_ids else []
        restored_reserved = 0
        for reservation in reservations:
            shipped = sum(
                item.quantity
                for item in originals
                if item.finished_stock_reservation_id == reservation.id
            )
            if reservation.shipped_quantity < shipped:
                raise DomainError("finished_reservation_balance_invalid", "成品占用账实不一致", status_code=409)
            restored_reserved += shipped + reservation.released_quantity
            session.scalar(select(func.set_config(
                "zzerp.finished_shipment_reversal_reservation_id",
                str(reservation.id),
                True,
            )))
            reservation.shipped_quantity -= shipped
            reservation.released_quantity = 0
            reservation.updated_at = utc_now()
            session.flush([reservation])

        total = sum(item.quantity for item in originals)
        running = stock.quantity
        stock.quantity += total
        stock.reserved_quantity += restored_reserved
        stock.revision += 1
        stock.updated_at = utc_now()
        reversal_group = f"shipment-reversal:{selected.operation_group_no}"
        correction_reason = (reason or "").strip() or "客户发货冲销"
        for original in originals:
            after = running + original.quantity
            session.add(FinishedStockTransaction(
                finished_stock_id=stock.id,
                finished_receipt_id=None,
                customer_order_id=order.id,
                customer_order_item_id=order_item.id,
                finished_stock_reservation_id=original.finished_stock_reservation_id,
                operation_group_no=reversal_group,
                reversal_of_transaction_id=original.id,
                transaction_type="customer_shipment_reversal",
                quantity=original.quantity,
                quantity_before=running,
                quantity_after=after,
                actor_username=actor,
                reason=correction_reason,
            ))
            running = after
        reopen_order_after_shipment_reversal(session, order.id)
        session.flush()
        product = session.get(Product, order_item.product_id)
        if product is None:
            raise DomainError("product_not_found", "产品不存在", status_code=409)
        return _serialize_candidate(
            order_item,
            order,
            product,
            stock,
            _item_shipped_quantity(session, order_item.id),
            _item_open_reservation_quantity(session, order_item.id),
        )


def _serialize_candidate(
    order_item: CustomerOrderItem,
    order: CustomerOrder,
    product: Product,
    stock: FinishedStock | None,
    shipped_quantity: int,
    reserved_quantity: int,
) -> dict:
    physical_quantity = stock.quantity if stock is not None else 0
    total_reserved_quantity = stock.reserved_quantity if stock is not None else 0
    unreserved_quantity = physical_quantity - total_reserved_quantity
    outstanding_quantity = max(order_item.quantity - int(shipped_quantity), 0)
    return {
        "customer_order_id": order.id,
        "customer_order_no": order.customer_order_no,
        "order_status": order.status,
        "customer_order_item_id": order_item.id,
        "item_code": product.factory_code,
        "item_name": product.product_name,
        "product_version": order_item.product_version,
        "required_quantity": order_item.quantity,
        "reserved_quantity": int(reserved_quantity),
        "unreserved_quantity": unreserved_quantity,
        "available_quantity": int(reserved_quantity) + unreserved_quantity,
        "shipped_quantity": int(shipped_quantity),
        "outstanding_quantity": outstanding_quantity,
    }


def _open_reservation_quantity(reservation: FinishedStockReservation | None) -> int:
    if reservation is None:
        return 0
    return (
        reservation.reserved_quantity
        - reservation.shipped_quantity
        - reservation.released_quantity
    )


def _release_open_reservation(
    stock: FinishedStock,
    reservation: FinishedStockReservation | None,
) -> None:
    open_quantity = _open_reservation_quantity(reservation)
    if reservation is None or open_quantity <= 0:
        return
    if stock.reserved_quantity < open_quantity:
        raise DomainError(
            "finished_reservation_balance_invalid",
            "成品库存占用账实不一致",
            status_code=409,
        )
    now = utc_now()
    reservation.released_quantity += open_quantity
    reservation.updated_at = now
    stock.reserved_quantity -= open_quantity
    stock.revision += 1
    stock.updated_at = now


def _item_shipped_quantity(session: Session, customer_order_item_id: int) -> int:
    return int(session.scalar(
        select(func.coalesce(func.sum(_shipment_signed_quantity()), 0)).where(
            FinishedStockTransaction.customer_order_item_id == customer_order_item_id,
            FinishedStockTransaction.transaction_type.in_((
                "customer_shipment", "customer_shipment_reversal"
            )),
        )
    ) or 0)


def _item_open_reservation_quantity(session: Session, customer_order_item_id: int) -> int:
    return int(session.scalar(
        select(func.coalesce(func.sum(
            FinishedStockReservation.reserved_quantity
            - FinishedStockReservation.shipped_quantity
            - FinishedStockReservation.released_quantity
        ), 0)).where(
            FinishedStockReservation.customer_order_item_id == customer_order_item_id,
        )
    ) or 0)


def _order_is_fully_shipped(session: Session, customer_order_id: int) -> bool:
    shipped_totals = _shipped_totals_subquery()
    states = list(session.execute(
        select(
            CustomerOrderItem.quantity,
            func.coalesce(shipped_totals.c.quantity, 0),
        )
        .outerjoin(
            shipped_totals,
            shipped_totals.c.customer_order_item_id == CustomerOrderItem.id,
        )
        .where(CustomerOrderItem.customer_order_id == customer_order_id)
        .order_by(CustomerOrderItem.id)
    ))
    return bool(states) and all(shipped >= required for required, shipped in states)


def _shipped_totals_subquery():
    return (
        select(
            FinishedStockTransaction.customer_order_item_id.label("customer_order_item_id"),
            func.sum(_shipment_signed_quantity()).label("quantity"),
        )
        .where(FinishedStockTransaction.transaction_type.in_((
            "customer_shipment", "customer_shipment_reversal"
        )))
        .group_by(FinishedStockTransaction.customer_order_item_id)
        .subquery()
    )


def _shipment_signed_quantity():
    return case(
        (FinishedStockTransaction.transaction_type == "customer_shipment", FinishedStockTransaction.quantity),
        else_=-FinishedStockTransaction.quantity,
    )


def _open_reservation_totals_subquery():
    return (
        select(
            FinishedStockReservation.customer_order_item_id.label("customer_order_item_id"),
            func.sum(
                FinishedStockReservation.reserved_quantity
                - FinishedStockReservation.shipped_quantity
                - FinishedStockReservation.released_quantity
            ).label("quantity"),
        )
        .group_by(FinishedStockReservation.customer_order_item_id)
        .subquery()
    )


__all__ = [
    "list_finished_shipment_candidates",
    "order_item_shipped_quantities",
    "reverse_finished_shipment",
    "ship_finished_order_item",
]
