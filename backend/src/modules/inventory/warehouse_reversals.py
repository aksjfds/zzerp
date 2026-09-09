"""Restricted reversal commands for temporary warehouse operations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from domain.warehouse import (
    WAREHOUSE_OPERATION_FAILED,
    WAREHOUSE_OPERATION_OUTBOUND,
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_OPERATION_UNCERTAIN,
    WAREHOUSE_SOURCE_QC_INVENTORY,
    WarehouseMutationResult,
    WarehouseStockIdentity,
)
from modules.errors import DomainError
from modules.inventory.persistence import WarehouseOperation
from modules.inventory.warehouse_contracts import WarehouseGatewayFactory
from modules.inventory.warehouse_gateway import PostgreSQLWarehouseGateway, WarehouseStockDeduction, WarehouseWriteRejected, WarehouseWriteUncertain
from modules.inventory.warehouse_operation_support import (
    _finish_failed_operation,
    _finish_succeeded_operation,
    _group_result,
    _new_reversal_operation,
)


def reverse_warehouse_operation_group(
    session: Session,
    *,
    original_group_no: str,
    reversal_group_no: str,
    actor_username: str,
    gateway_factory: WarehouseGatewayFactory = PostgreSQLWarehouseGateway,
) -> WarehouseMutationResult:
    """Reverse one successful project-owned warehouse operation group exactly once."""
    actor = actor_username.strip()
    if not actor or actor != actor_username:
        raise DomainError("warehouse_actor_invalid", "仓库操作人不能为空或包含首尾空格")
    originals = list(session.scalars(
        select(WarehouseOperation)
        .where(WarehouseOperation.operation_group_no == original_group_no)
        .order_by(WarehouseOperation.id)
        .with_for_update()
    ))
    if not originals:
        raise DomainError("warehouse_operation_not_found", "原仓库操作不存在", status_code=404)
    if any(operation.status != WAREHOUSE_OPERATION_SUCCEEDED for operation in originals):
        raise DomainError(
            "warehouse_operation_not_reversible",
            "只有全部成功的仓库操作才能冲销",
            status_code=409,
        )
    existing = list(session.scalars(
        select(WarehouseOperation)
        .where(WarehouseOperation.reversal_of_operation_id.in_([item.id for item in originals]))
        .order_by(WarehouseOperation.id)
    ))
    if existing:
        if len(existing) != len(originals) or any(
            item.operation_group_no != reversal_group_no for item in existing
        ):
            raise DomainError(
                "warehouse_operation_already_reversed",
                "原仓库操作已经冲销",
                status_code=409,
            )
        return _group_result(session, reversal_group_no)

    gateway = gateway_factory(session)
    for index, original in enumerate(originals):
        reversal = _new_reversal_operation(
            original,
            reversal_group_no=reversal_group_no,
            index=index,
            actor_username=actor,
        )
        session.add(reversal)
        session.flush()
        try:
            if original.operation_type == WAREHOUSE_OPERATION_OUTBOUND:
                changed = gateway.increase_stock(
                    identity=WarehouseStockIdentity(
                        item_code=original.item_code,
                        product_version=original.product_version,
                        item_type=original.item_type,
                        completion_status=original.completion_status,
                        warehouse_code=original.warehouse_code,
                    ),
                    item_name=original.item_name,
                    specification=original.specification,
                    warehouse_name=original.warehouse_name,
                    quantity=original.quantity,
                )
                quantity_before = changed.quantity - original.quantity
            else:
                if original.warehouse_stock_id is None:
                    raise WarehouseWriteRejected("原入库操作缺少库存记录")
                before_rows = gateway.lock_outbound_candidates(
                    item_code=original.item_code,
                    product_version=original.product_version,
                    item_type=original.item_type,
                    warehouse_code=original.warehouse_code,
                    completion_status_priority=(original.completion_status,),
                )
                before = next(
                    (row for row in before_rows if row.id == original.warehouse_stock_id),
                    None,
                )
                if before is None or before.quantity < original.quantity:
                    raise WarehouseWriteRejected("该批入库数量已被使用，不能冲销")
                changed = gateway.decrease_stocks((
                    WarehouseStockDeduction(original.warehouse_stock_id, original.quantity),
                ))[0]
                quantity_before = before.quantity
        except WarehouseWriteUncertain as error:
            return _finish_failed_operation(
                session, reversal, WAREHOUSE_OPERATION_UNCERTAIN, str(error)
            )
        except WarehouseWriteRejected as error:
            return _finish_failed_operation(
                session, reversal, WAREHOUSE_OPERATION_FAILED, str(error)
            )
        _finish_succeeded_operation(
            reversal,
            stock=changed,
            quantity=original.quantity,
            quantity_before=quantity_before,
        )
    session.flush()
    return _group_result(session, reversal_group_no)


def next_qc_inventory_operation_group(
    session: Session,
    *,
    work_order_batch_id: int,
) -> str:
    attempt = (
        session.scalar(
            select(func.count(WarehouseOperation.id)).where(
                WarehouseOperation.work_order_batch_id == work_order_batch_id,
                WarehouseOperation.source_type == WAREHOUSE_SOURCE_QC_INVENTORY,
            )
        )
        or 0
    ) + 1
    return f"qc:{work_order_batch_id}:inventory:{attempt}"


def reverse_latest_qc_inventory_operation(
    session: Session,
    *,
    work_order_batch_id: int,
    actor_username: str,
) -> WarehouseMutationResult:
    reversal = aliased(WarehouseOperation)
    original = session.scalar(
        select(WarehouseOperation)
        .where(
            WarehouseOperation.work_order_batch_id == work_order_batch_id,
            WarehouseOperation.source_type == WAREHOUSE_SOURCE_QC_INVENTORY,
            WarehouseOperation.status == WAREHOUSE_OPERATION_SUCCEEDED,
            ~select(reversal.id)
            .where(reversal.reversal_of_operation_id == WarehouseOperation.id)
            .exists(),
        )
        .order_by(WarehouseOperation.id.desc())
        .with_for_update()
    )
    if original is None:
        raise DomainError(
            "qc_inventory_operation_not_found",
            "质检入仓操作不存在或已经冲销",
            status_code=409,
        )
    return reverse_warehouse_operation_group(
        session,
        original_group_no=original.operation_group_no,
        reversal_group_no=f"{original.operation_group_no}:reversal",
        actor_username=actor_username,
    )
