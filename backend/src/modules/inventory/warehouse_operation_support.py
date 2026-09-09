"""Shared idempotency, validation, and snapshot logic for warehouse commands."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.time import utc_now
from domain.warehouse import (
    WAREHOUSE_CODE_MAIN,
    WAREHOUSE_NAME_MAIN,
    WAREHOUSE_OPERATION_FAILED,
    WAREHOUSE_OPERATION_INBOUND,
    WAREHOUSE_OPERATION_OUTBOUND,
    WAREHOUSE_OPERATION_PENDING,
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_OPERATION_UNCERTAIN,
    WAREHOUSE_SOURCE_PLAN_CONFIRMATION,
    WAREHOUSE_SOURCE_PRODUCTION_POSITION,
    WAREHOUSE_SOURCE_QC_INVENTORY,
    WAREHOUSE_SOURCE_REVERSAL,
    WAREHOUSE_UNIT_PCS,
    WarehouseMutationResult,
    WarehouseOperationContext,
    WarehouseOperationSnapshot,
    WarehouseStockSnapshot,
)
from modules.errors import DomainError
from modules.inventory.persistence import WarehouseOperation
from modules.inventory.warehouse_contracts import WarehouseInboundRequest, WarehouseOutboundRequest
from modules.inventory.warehouse_gateway import WarehouseStockDeduction


def _new_reversal_operation(
    original: WarehouseOperation,
    *,
    reversal_group_no: str,
    index: int,
    actor_username: str,
) -> WarehouseOperation:
    return WarehouseOperation(
        operation_group_no=reversal_group_no,
        operation_no=f"{reversal_group_no}:{index}",
        operation_type=(
            WAREHOUSE_OPERATION_INBOUND
            if original.operation_type == WAREHOUSE_OPERATION_OUTBOUND
            else WAREHOUSE_OPERATION_OUTBOUND
        ),
        source_type=WAREHOUSE_SOURCE_REVERSAL,
        reversal_of_operation_id=original.id,
        processing_state_id=original.processing_state_id,
        warehouse_stock_id=None,
        item_code=original.item_code,
        item_name=original.item_name,
        product_version=original.product_version,
        item_type=original.item_type,
        specification=original.specification,
        inventory_unit=original.inventory_unit,
        warehouse_code=original.warehouse_code,
        warehouse_name=original.warehouse_name,
        completion_status=original.completion_status,
        quantity=original.quantity,
        status=WAREHOUSE_OPERATION_PENDING,
        actor_username=actor_username,
    )


def _allocate_quantity(
    candidates: tuple[WarehouseStockSnapshot, ...],
    requested_quantity: int,
) -> tuple[WarehouseStockDeduction, ...]:
    remaining = requested_quantity
    allocations: list[WarehouseStockDeduction] = []
    for stock in candidates:
        quantity = min(stock.quantity, remaining)
        if quantity > 0:
            allocations.append(WarehouseStockDeduction(stock.id, quantity))
            remaining -= quantity
        if remaining == 0:
            break
    return tuple(allocations)


def _matches_inbound_result(
    stock: WarehouseStockSnapshot,
    request: WarehouseInboundRequest,
) -> bool:
    return (
        stock.item_code == request.item_code
        and stock.item_name == request.item_name
        and stock.product_version == request.product_version
        and stock.item_type == request.item_type
        and stock.specification == request.specification
        and stock.warehouse_code == WAREHOUSE_CODE_MAIN
        and stock.warehouse_name == WAREHOUSE_NAME_MAIN
        and stock.completion_status == request.completion_status
        and stock.quantity >= request.quantity
    )


def _matches_outbound_results(
    allocations: tuple[WarehouseStockDeduction, ...],
    changed_stocks: tuple[WarehouseStockSnapshot, ...],
    candidates: dict[int, WarehouseStockSnapshot],
) -> bool:
    if len(allocations) != len(changed_stocks):
        return False
    return all(
        changed.id == allocation.stock_id
        and allocation.stock_id in candidates
        and changed.quantity
        == candidates[allocation.stock_id].quantity - allocation.quantity
        for allocation, changed in zip(allocations, changed_stocks, strict=True)
    )


def _claim_operation(
    session: Session,
    *,
    operation_group_no: str,
    operation_type: str,
    context: WarehouseOperationContext,
    item_code: str,
    item_name: str,
    product_version: int,
    item_type: str,
    completion_status: str,
    processing_state_id: int,
    quantity: int,
    actor_username: str,
    specification: str,
) -> tuple[WarehouseOperation, bool]:
    operation_no = f"{operation_group_no}:0"
    statement = (
        insert(WarehouseOperation)
        .values(
            operation_group_no=operation_group_no,
            operation_no=operation_no,
            operation_type=operation_type,
            source_type=context.source_type,
            production_plan_id=context.production_plan_id,
            production_plan_item_id=context.production_plan_item_id,
            work_order_id=context.work_order_id,
            work_order_batch_id=context.work_order_batch_id,
            production_item_id=context.production_item_id,
            processing_state_id=processing_state_id,
            warehouse_stock_id=None,
            item_code=item_code,
            item_name=item_name,
            product_version=product_version,
            item_type=item_type,
            specification=specification,
            inventory_unit=WAREHOUSE_UNIT_PCS,
            warehouse_code=WAREHOUSE_CODE_MAIN,
            warehouse_name=WAREHOUSE_NAME_MAIN,
            completion_status=completion_status,
            quantity=quantity,
            status=WAREHOUSE_OPERATION_PENDING,
            actor_username=actor_username,
        )
        .on_conflict_do_nothing(index_elements=[WarehouseOperation.operation_no])
        .returning(WarehouseOperation.id)
    )
    operation_id = session.scalar(statement)
    created = operation_id is not None
    operation = session.get(
        WarehouseOperation,
        operation_id,
        with_for_update=True,
    ) if created else session.scalar(
        select(WarehouseOperation)
        .where(WarehouseOperation.operation_no == operation_no)
        .with_for_update()
    )
    if operation is None:
        raise DomainError(
            "warehouse_operation_claim_failed",
            "无法认领仓库操作，请刷新后重试",
            status_code=409,
        )
    return operation, created


def _existing_result(
    session: Session,
    operation: WarehouseOperation,
    requested_quantity: int,
) -> WarehouseMutationResult:
    result = _group_result(session, operation.operation_group_no)
    if result.requested_quantity != requested_quantity:
        raise DomainError(
            "warehouse_operation_request_conflict",
            "相同仓库操作号对应的请求数量不一致",
            status_code=409,
        )
    return result


def _finish_failed_operation(
    session: Session,
    operation: WarehouseOperation,
    status: str,
    error_message: str,
) -> WarehouseMutationResult:
    operation.status = status
    operation.error_message = error_message
    operation.executed_at = utc_now()
    session.flush()
    return _group_result(session, operation.operation_group_no)


def _finish_succeeded_operation(
    operation: WarehouseOperation,
    *,
    stock: WarehouseStockSnapshot,
    quantity: int,
    quantity_before: int,
) -> None:
    operation.warehouse_stock_id = stock.id
    operation.item_code = stock.item_code
    operation.item_name = stock.item_name
    operation.product_version = stock.product_version
    operation.item_type = stock.item_type
    operation.specification = stock.specification
    operation.inventory_unit = stock.inventory_unit
    operation.warehouse_code = stock.warehouse_code
    operation.warehouse_name = stock.warehouse_name
    operation.completion_status = stock.completion_status
    operation.quantity = quantity
    operation.quantity_before = quantity_before
    operation.quantity_after = stock.quantity
    operation.status = WAREHOUSE_OPERATION_SUCCEEDED
    operation.error_message = None
    operation.executed_at = utc_now()


def _new_operation_line(first: WarehouseOperation, index: int) -> WarehouseOperation:
    return WarehouseOperation(
        operation_group_no=first.operation_group_no,
        operation_no=f"{first.operation_group_no}:{index}",
        operation_type=first.operation_type,
        source_type=first.source_type,
        production_plan_id=first.production_plan_id,
        production_plan_item_id=first.production_plan_item_id,
        work_order_id=first.work_order_id,
        work_order_batch_id=first.work_order_batch_id,
        production_item_id=first.production_item_id,
        processing_state_id=first.processing_state_id,
        item_code=first.item_code,
        item_name=first.item_name,
        product_version=first.product_version,
        item_type=first.item_type,
        specification=first.specification,
        inventory_unit=first.inventory_unit,
        warehouse_code=first.warehouse_code,
        warehouse_name=first.warehouse_name,
        completion_status=first.completion_status,
        quantity=first.quantity,
        status=WAREHOUSE_OPERATION_PENDING,
        actor_username=first.actor_username,
    )


def _group_result(
    session: Session,
    operation_group_no: str,
) -> WarehouseMutationResult:
    operations = list(session.scalars(
        select(WarehouseOperation)
        .where(WarehouseOperation.operation_group_no == operation_group_no)
        .order_by(WarehouseOperation.id)
    ))
    snapshots = tuple(_operation_snapshot(operation) for operation in operations)
    statuses = {operation.status for operation in operations}
    if WAREHOUSE_OPERATION_UNCERTAIN in statuses:
        status = WAREHOUSE_OPERATION_UNCERTAIN
    elif WAREHOUSE_OPERATION_FAILED in statuses:
        status = WAREHOUSE_OPERATION_FAILED
    elif statuses == {WAREHOUSE_OPERATION_SUCCEEDED}:
        status = WAREHOUSE_OPERATION_SUCCEEDED
    else:
        status = WAREHOUSE_OPERATION_PENDING
    processed_quantity = sum(
        operation.quantity
        for operation in operations
        if operation.status == WAREHOUSE_OPERATION_SUCCEEDED
    )
    requested_quantity = (
        processed_quantity
        if status == WAREHOUSE_OPERATION_SUCCEEDED
        else operations[0].quantity
    )
    error_message = next(
        (operation.error_message for operation in operations if operation.error_message),
        None,
    )
    return WarehouseMutationResult(
        operation_group_no=operation_group_no,
        status=status,
        requested_quantity=requested_quantity,
        processed_quantity=processed_quantity,
        operations=snapshots,
        error_message=error_message,
    )


def _ensure_same_request(
    operation: WarehouseOperation,
    *,
    operation_type: str,
    context: WarehouseOperationContext,
    item_code: str,
    item_name: str,
    product_version: int,
    item_type: str,
    completion_status: str | None,
    processing_state_id: int | None,
    specification: str | None,
) -> None:
    same_context = (
        operation.source_type == context.source_type
        and operation.production_plan_id == context.production_plan_id
        and operation.production_plan_item_id == context.production_plan_item_id
        and operation.work_order_id == context.work_order_id
        and operation.work_order_batch_id == context.work_order_batch_id
        and operation.production_item_id == context.production_item_id
    )
    same_item = (
        operation.operation_type == operation_type
        and operation.item_code == item_code
        and operation.item_name == item_name
        and operation.product_version == product_version
        and operation.item_type == item_type
        and (
            processing_state_id is None
            or operation.processing_state_id == processing_state_id
        )
        and (specification is None or operation.specification == specification)
        and (
            completion_status is None
            or operation.completion_status == completion_status
        )
    )
    if not same_context or not same_item:
        raise DomainError(
            "warehouse_operation_request_conflict",
            "相同仓库操作号对应了不同业务请求",
            status_code=409,
        )


def _operation_snapshot(operation: WarehouseOperation) -> WarehouseOperationSnapshot:
    return WarehouseOperationSnapshot(
        id=operation.id,
        operation_group_no=operation.operation_group_no,
        operation_no=operation.operation_no,
        operation_type=operation.operation_type,
        source_type=operation.source_type,
        production_plan_id=operation.production_plan_id,
        production_plan_item_id=operation.production_plan_item_id,
        work_order_id=operation.work_order_id,
        work_order_batch_id=operation.work_order_batch_id,
        production_item_id=operation.production_item_id,
        processing_state_id=operation.processing_state_id,
        reversal_of_operation_id=operation.reversal_of_operation_id,
        warehouse_stock_id=operation.warehouse_stock_id,
        item_code=operation.item_code,
        item_name=operation.item_name,
        product_version=operation.product_version,
        item_type=operation.item_type,
        specification=operation.specification,
        inventory_unit=operation.inventory_unit,
        warehouse_code=operation.warehouse_code,
        warehouse_name=operation.warehouse_name,
        completion_status=operation.completion_status,
        quantity=operation.quantity,
        quantity_before=operation.quantity_before,
        quantity_after=operation.quantity_after,
        status=operation.status,
        actor_username=operation.actor_username,
        error_message=operation.error_message,
        created_at=operation.created_at,
        executed_at=operation.executed_at,
        manual_reviewed_at=operation.manual_reviewed_at,
        manual_reviewed_by=operation.manual_reviewed_by,
        manual_review_note=operation.manual_review_note,
    )


def _validate_inbound_request(request: WarehouseInboundRequest) -> None:
    _validate_request_fields(request)
    if request.processing_state_id <= 0:
        raise DomainError("warehouse_processing_state_invalid", "物料加工状态无效")
    if (
        not request.completion_status
        or request.completion_status.strip() != request.completion_status
    ):
        raise DomainError("warehouse_completion_status_invalid", "加工状态不能为空或包含首尾空格")
    if request.specification != "":
        raise DomainError("warehouse_specification_invalid", "当前仓库规格必须为空")
    if request.context.source_type not in {
        WAREHOUSE_SOURCE_QC_INVENTORY,
        WAREHOUSE_SOURCE_PRODUCTION_POSITION,
    }:
        raise DomainError("warehouse_inbound_source_invalid", "该业务来源不能执行入库")
    _validate_context(request.context)


def _validate_outbound_request(request: WarehouseOutboundRequest) -> None:
    _validate_request_fields(request)
    if request.context.source_type != WAREHOUSE_SOURCE_PLAN_CONFIRMATION:
        raise DomainError("warehouse_outbound_source_invalid", "该业务来源不能执行出库")
    if not request.completion_status_priority or any(
        not status or status.strip() != status
        for status in request.completion_status_priority
    ):
        raise DomainError("warehouse_status_priority_invalid", "库存加工状态顺序不能为空")
    if len(set(request.completion_status_priority)) != len(
        request.completion_status_priority
    ):
        raise DomainError("warehouse_status_priority_duplicate", "库存加工状态顺序不能重复")
    state_ids = dict(request.processing_state_ids)
    if (
        len(state_ids) != len(request.processing_state_ids)
        or set(state_ids) != set(request.completion_status_priority)
        or any(state_id <= 0 for state_id in state_ids.values())
    ):
        raise DomainError("warehouse_processing_state_invalid", "库存加工状态映射不完整")
    _validate_context(request.context)


def _validate_request_fields(request) -> None:
    if (
        request.operation_group_no.strip() != request.operation_group_no
        or not request.operation_group_no
    ):
        raise DomainError("warehouse_operation_no_invalid", "仓库操作号不能为空或包含首尾空格")
    if request.item_code.strip() != request.item_code or not request.item_code:
        raise DomainError("warehouse_item_code_invalid", "仓库品号不能为空或包含首尾空格")
    if request.item_name.strip() != request.item_name or not request.item_name:
        raise DomainError("warehouse_item_name_invalid", "仓库品名不能为空或包含首尾空格")
    if request.item_type not in {"part", "assembly"}:
        raise DomainError("warehouse_item_type_invalid", "仓库物料类型无效")
    if request.product_version <= 0:
        raise DomainError("warehouse_product_version_invalid", "产品版本必须大于0")
    if request.quantity <= 0:
        raise DomainError("warehouse_quantity_invalid", "仓库操作数量必须大于0")
    if request.actor_username.strip() != request.actor_username or not request.actor_username:
        raise DomainError("warehouse_actor_invalid", "仓库操作人不能为空或包含首尾空格")


def _validate_context(context: WarehouseOperationContext) -> None:
    plan_context = (
        context.production_plan_id is not None
        and context.production_plan_item_id is not None
        and context.work_order_id is None
        and context.work_order_batch_id is None
        and context.production_item_id is None
    )
    qc_context = (
        context.production_plan_id is None
        and context.production_plan_item_id is None
        and context.work_order_id is not None
        and context.work_order_batch_id is not None
        and context.production_item_id is not None
    )
    position_context = (
        context.production_plan_id is None
        and context.production_plan_item_id is None
        and context.work_order_id is None
        and context.work_order_batch_id is None
        and context.production_item_id is not None
    )
    valid = (
        context.source_type == WAREHOUSE_SOURCE_PLAN_CONFIRMATION and plan_context
    ) or (
        context.source_type == WAREHOUSE_SOURCE_QC_INVENTORY and qc_context
    ) or (
        context.source_type == WAREHOUSE_SOURCE_PRODUCTION_POSITION and position_context
    )
    if not valid:
        raise DomainError("warehouse_operation_context_invalid", "仓库操作来源与业务引用不匹配")
