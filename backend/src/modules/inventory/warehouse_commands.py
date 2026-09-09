"""Idempotent temporary warehouse inbound, outbound, and review commands."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.time import utc_now
from domain.warehouse import (
    WAREHOUSE_CODE_MAIN,
    WAREHOUSE_NAME_MAIN,
    WAREHOUSE_OPERATION_FAILED,
    WAREHOUSE_OPERATION_INBOUND,
    WAREHOUSE_OPERATION_OUTBOUND,
    WAREHOUSE_OPERATION_UNCERTAIN,
    WarehouseMutationResult,
    WarehouseOperationSnapshot,
    WarehouseStockIdentity,
)
from modules.errors import DomainError
from modules.inventory.persistence import WarehouseOperation
from modules.inventory.warehouse_contracts import WarehouseInboundRequest, WarehouseOutboundRequest, WarehouseGatewayFactory
from modules.inventory.warehouse_gateway import PostgreSQLWarehouseGateway, WarehouseWriteRejected, WarehouseWriteUncertain
from modules.inventory.warehouse_operation_support import (
    _allocate_quantity,
    _claim_operation,
    _ensure_same_request,
    _existing_result,
    _finish_failed_operation,
    _finish_succeeded_operation,
    _group_result,
    _matches_inbound_result,
    _matches_outbound_results,
    _new_operation_line,
    _operation_snapshot,
    _validate_inbound_request,
    _validate_outbound_request,
)


def review_uncertain_warehouse_operation(
    session: Session,
    *,
    operation_group_no: str,
    reviewer_username: str,
    review_note: str,
) -> tuple[WarehouseOperationSnapshot, ...]:
    if not reviewer_username.strip() or reviewer_username.strip() != reviewer_username:
        raise DomainError("warehouse_reviewer_invalid", "核对人不能为空或包含首尾空格")
    if not review_note.strip() or review_note.strip() != review_note:
        raise DomainError("warehouse_review_note_invalid", "核对说明不能为空或包含首尾空格")
    operations = list(session.scalars(
        select(WarehouseOperation)
        .where(WarehouseOperation.operation_group_no == operation_group_no)
        .order_by(WarehouseOperation.id)
        .with_for_update()
    ))
    if not operations:
        raise DomainError("warehouse_operation_not_found", "仓库操作不存在", status_code=404)
    if any(operation.status != WAREHOUSE_OPERATION_UNCERTAIN for operation in operations):
        raise DomainError(
            "warehouse_operation_not_uncertain",
            "只有结果不确定的仓库操作可以人工核对",
            status_code=409,
        )
    reviewed_at = utc_now()
    for operation in operations:
        if operation.manual_reviewed_at is not None:
            if (
                operation.manual_reviewed_by != reviewer_username
                or operation.manual_review_note != review_note
            ):
                raise DomainError(
                    "warehouse_operation_already_reviewed",
                    "该仓库操作已由人工核对",
                    status_code=409,
                )
            continue
        operation.manual_reviewed_at = reviewed_at
        operation.manual_reviewed_by = reviewer_username
        operation.manual_review_note = review_note
    session.flush()
    return tuple(_operation_snapshot(operation) for operation in operations)


def receive_c01_stock(
    session: Session,
    request: WarehouseInboundRequest,
    *,
    gateway_factory: WarehouseGatewayFactory = PostgreSQLWarehouseGateway,
) -> WarehouseMutationResult:
    _validate_inbound_request(request)
    operation, created = _claim_operation(
        session,
        operation_group_no=request.operation_group_no,
        operation_type=WAREHOUSE_OPERATION_INBOUND,
        context=request.context,
        item_code=request.item_code,
        item_name=request.item_name,
        product_version=request.product_version,
        item_type=request.item_type,
        completion_status=request.completion_status,
        processing_state_id=request.processing_state_id,
        quantity=request.quantity,
        actor_username=request.actor_username,
        specification=request.specification,
    )
    if not created:
        _ensure_same_request(
            operation,
            operation_type=WAREHOUSE_OPERATION_INBOUND,
            context=request.context,
            item_code=request.item_code,
            item_name=request.item_name,
            product_version=request.product_version,
            item_type=request.item_type,
            completion_status=request.completion_status,
            processing_state_id=request.processing_state_id,
            specification=request.specification,
        )
        return _existing_result(session, operation, request.quantity)

    gateway = gateway_factory(session)
    identity = WarehouseStockIdentity(
        item_code=request.item_code,
        product_version=request.product_version,
        item_type=request.item_type,
        completion_status=request.completion_status,
        warehouse_code=WAREHOUSE_CODE_MAIN,
    )
    try:
        stock = gateway.increase_stock(
            identity=identity,
            item_name=request.item_name,
            specification=request.specification,
            warehouse_name=WAREHOUSE_NAME_MAIN,
            quantity=request.quantity,
        )
    except WarehouseWriteUncertain as error:
        return _finish_failed_operation(
            session, operation, WAREHOUSE_OPERATION_UNCERTAIN, str(error)
        )
    except WarehouseWriteRejected as error:
        return _finish_failed_operation(
            session, operation, WAREHOUSE_OPERATION_FAILED, str(error)
        )
    if not _matches_inbound_result(stock, request):
        return _finish_failed_operation(
            session,
            operation,
            WAREHOUSE_OPERATION_UNCERTAIN,
            "仓库返回的入库结果与请求不一致，需要人工核对",
        )

    _finish_succeeded_operation(
        operation,
        stock=stock,
        quantity=request.quantity,
        quantity_before=stock.quantity - request.quantity,
    )
    session.flush()
    return _group_result(session, request.operation_group_no)


def withdraw_c01_stock(
    session: Session,
    request: WarehouseOutboundRequest,
    *,
    gateway_factory: WarehouseGatewayFactory = PostgreSQLWarehouseGateway,
) -> WarehouseMutationResult:
    _validate_outbound_request(request)
    operation, created = _claim_operation(
        session,
        operation_group_no=request.operation_group_no,
        operation_type=WAREHOUSE_OPERATION_OUTBOUND,
        context=request.context,
        item_code=request.item_code,
        item_name=request.item_name,
        product_version=request.product_version,
        item_type=request.item_type,
        completion_status=request.completion_status_priority[0],
        processing_state_id=dict(request.processing_state_ids)[request.completion_status_priority[0]],
        quantity=request.quantity,
        actor_username=request.actor_username,
        specification="",
    )
    if not created:
        _ensure_same_request(
            operation,
            operation_type=WAREHOUSE_OPERATION_OUTBOUND,
            context=request.context,
            item_code=request.item_code,
            item_name=request.item_name,
            product_version=request.product_version,
            item_type=request.item_type,
            completion_status=None,
            processing_state_id=None,
            specification=None,
        )
        return _existing_result(session, operation, request.quantity)

    gateway = gateway_factory(session)
    candidates = gateway.lock_outbound_candidates(
        item_code=request.item_code,
        product_version=request.product_version,
        item_type=request.item_type,
        warehouse_code=WAREHOUSE_CODE_MAIN,
        completion_status_priority=request.completion_status_priority,
    )
    if any(stock.item_name != request.item_name for stock in candidates):
        return _finish_failed_operation(
            session,
            operation,
            WAREHOUSE_OPERATION_FAILED,
            "相同品号和版本的仓库品名不一致",
        )
    allocations = _allocate_quantity(candidates, request.quantity)
    if sum(allocation.quantity for allocation in allocations) != request.quantity:
        return _finish_failed_operation(
            session,
            operation,
            WAREHOUSE_OPERATION_FAILED,
            "当前可用仓库库存不足",
        )

    try:
        changed_stocks = gateway.decrease_stocks(allocations)
    except WarehouseWriteUncertain as error:
        return _finish_failed_operation(
            session, operation, WAREHOUSE_OPERATION_UNCERTAIN, str(error)
        )
    except WarehouseWriteRejected as error:
        return _finish_failed_operation(
            session, operation, WAREHOUSE_OPERATION_FAILED, str(error)
        )

    candidate_by_id = {stock.id: stock for stock in candidates}
    if not _matches_outbound_results(
        allocations,
        changed_stocks,
        candidate_by_id,
    ):
        return _finish_failed_operation(
            session,
            operation,
            WAREHOUSE_OPERATION_UNCERTAIN,
            "仓库返回的出库结果与请求不一致，需要人工核对",
        )
    for index, (allocation, changed_stock) in enumerate(
        zip(allocations, changed_stocks, strict=True)
    ):
        target = operation if index == 0 else _new_operation_line(operation, index)
        before = candidate_by_id[allocation.stock_id]
        target.processing_state_id = dict(request.processing_state_ids)[before.completion_status]
        _finish_succeeded_operation(
            target,
            stock=changed_stock,
            quantity=allocation.quantity,
            quantity_before=before.quantity,
        )
        if index:
            session.add(target)
    session.flush()
    return _group_result(session, request.operation_group_no)
