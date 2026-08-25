"""Application orchestration for completed-plan production-position storage."""

from database import SessionLocal
from domain.warehouse import (
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_SOURCE_PRODUCTION_POSITION,
    WarehouseOperationContext,
)
from modules.errors import DomainError
from modules.inventory.warehouse_api import (
    WarehouseInboundRequest,
    list_warehouse_operations,
    receive_c01_stock,
)
from modules.organization.read_api import (
    DepartmentView,
    get_department_ids_by_codes,
    get_department_views_by_codes,
)
from modules.planning.execution_api import (
    completed_plan_order_item_ids,
    ensure_production_plan_completed,
)
from modules.production_core.position_inventory_api import (
    ProductionPositionCandidate,
    consume_position_for_warehouse,
    department_position_order_item_ids,
    get_available_production_position,
    list_available_production_positions,
    lock_production_position,
    position_inventory_movement_matches,
)


def list_completed_plan_positions(department_code: str) -> list[dict]:
    if department_code == "qc":
        return []
    with SessionLocal() as session:
        department = _department(session, department_code)
        order_item_ids = department_position_order_item_ids(session, department.id)
        completed_ids = completed_plan_order_item_ids(session, order_item_ids)
        return [
            _serialize_candidate(candidate)
            for candidate in list_available_production_positions(
                session,
                department_id=department.id,
                department_code=department_code,
                completed_order_item_ids=completed_ids,
            )
        ]


def store_completed_plan_position(
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    position_version: str,
    quantity: int,
    actor_username: str,
) -> dict:
    operation_group_no = _operation_group_no(
        department_code,
        production_item_id,
        flow_node_id,
        source_flow_node_id,
        position_version,
        quantity,
    )
    with SessionLocal.begin() as session:
        existing = _existing_storage_result(
            session,
            operation_group_no,
            production_item_id,
        )
        if existing is not None:
            return existing
        department = _department(session, department_code)
        candidate = get_available_production_position(
            session,
            department_id=department.id,
            department_code=department_code,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
        )
        if candidate is None:
            raise DomainError(
                "warehouse_storage_source_empty",
                "当前生产位置没有可入库数量",
                status_code=409,
            )
        if candidate.position_version != position_version:
            raise DomainError(
                "warehouse_storage_position_changed",
                "当前生产位置数量已变化，请刷新后重试",
                status_code=409,
            )
        if quantity > candidate.available_quantity:
            raise DomainError(
                "warehouse_storage_quantity_exceeds_available",
                f"最多可存入仓库 {candidate.available_quantity} 件",
                status_code=409,
            )
        ensure_production_plan_completed(
            session,
            candidate.customer_order_item_id,
        )
        result = receive_c01_stock(
            session,
            WarehouseInboundRequest(
                operation_group_no=operation_group_no,
                context=WarehouseOperationContext(
                    source_type=WAREHOUSE_SOURCE_PRODUCTION_POSITION,
                    production_item_id=production_item_id,
                ),
                item_code=candidate.item_code,
                item_name=candidate.item_name,
                product_version=candidate.product_version,
                item_type=candidate.item_type,
                completion_status=candidate.completion_status,
                quantity=quantity,
                actor_username=actor_username,
            ),
        )
        if result.status != WAREHOUSE_OPERATION_SUCCEEDED or len(result.operations) != 1:
            raise DomainError(
                "warehouse_inbound_failed",
                result.error_message or "仓库入库未成功，请核对后重试",
                status_code=409,
            )
        operation = result.operations[0]
        if operation.warehouse_stock_id is None:
            raise DomainError(
                "warehouse_inbound_result_invalid",
                "仓库入库结果不完整",
                status_code=409,
            )
        try:
            locked = lock_production_position(
                session,
                department_id=department.id,
                department_code=department_code,
                production_item_id=production_item_id,
                flow_node_id=flow_node_id,
                source_flow_node_id=source_flow_node_id,
                position_version=position_version,
                quantity=quantity,
            )
        except DomainError as error:
            if error.code != "warehouse_storage_position_changed":
                raise
            replayed = _completed_storage_replay(
                session,
                operation_group_no,
                production_item_id,
            )
            if replayed is not None:
                return replayed
            raise
        warehouse_department_id = get_department_ids_by_codes(
            session,
            {"warehouse"},
        ).get("warehouse")
        if warehouse_department_id is None:
            raise DomainError("department_not_found", "仓库部门不存在")
        consume_position_for_warehouse(
            session,
            locked,
            quantity=quantity,
            warehouse_department_id=warehouse_department_id,
            warehouse_operation_id=operation.id,
        )
        session.flush()
        return _storage_response(operation)


def _department(session, department_code: str) -> DepartmentView:
    department = next(
        iter(get_department_views_by_codes(session, {department_code})),
        None,
    )
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    return department


def _serialize_candidate(candidate: ProductionPositionCandidate) -> dict:
    return {
        "key": (
            f"position:{candidate.production_item_id}:"
            f"{candidate.flow_node_id}:{candidate.source_flow_node_id}"
        ),
        "production_item_id": candidate.production_item_id,
        "customer_order_no": candidate.customer_order_no,
        "product_code": candidate.product_code,
        "product_name": candidate.product_name,
        "product_version": candidate.product_version,
        "item_type": candidate.item_type,
        "item_code": candidate.item_code,
        "item_name": candidate.item_name,
        "department_code": candidate.department_code,
        "flow_node_id": candidate.flow_node_id,
        "source_flow_node_id": candidate.source_flow_node_id,
        "current_node_label": candidate.current_node_label,
        "completed_flow_node_id": candidate.completed_flow_node_id,
        "completion_status": candidate.completion_status,
        "available_quantity": candidate.available_quantity,
        "position_version": candidate.position_version,
    }


def _operation_group_no(
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    position_version: str,
    quantity: int,
) -> str:
    return (
        f"position:{department_code}:{production_item_id}:{flow_node_id}:"
        f"{source_flow_node_id}:{position_version}:quantity:{quantity}"
    )


def _existing_storage_result(
    session,
    operation_group_no: str,
    production_item_id: int,
) -> dict | None:
    operation = _storage_operation(
        session,
        operation_group_no,
        production_item_id,
    )
    if operation is None:
        return None
    if operation.status != WAREHOUSE_OPERATION_SUCCEEDED:
        raise DomainError(
            "warehouse_operation_incomplete",
            operation.error_message or "仓库操作尚未明确成功，请核对后处理",
            status_code=409,
        )
    if not position_inventory_movement_matches(
        session,
        warehouse_operation_id=operation.id,
        production_item_id=production_item_id,
    ):
        raise DomainError(
            "warehouse_operation_inconsistent",
            "仓库操作与生产位置流水不一致，请核对后处理",
            status_code=409,
        )
    return _storage_response(operation)


def _completed_storage_replay(
    session,
    operation_group_no: str,
    production_item_id: int,
) -> dict | None:
    operation = _storage_operation(
        session,
        operation_group_no,
        production_item_id,
    )
    if operation is None:
        return None
    if (
        operation.status != WAREHOUSE_OPERATION_SUCCEEDED
        or not position_inventory_movement_matches(
            session,
            warehouse_operation_id=operation.id,
            production_item_id=production_item_id,
        )
    ):
        return None
    return _storage_response(operation)


def _storage_operation(
    session,
    operation_group_no: str,
    production_item_id: int,
):
    operations = list_warehouse_operations(
        session,
        operation_group_no=operation_group_no,
        limit=2,
    )
    if not operations:
        return None
    if len(operations) != 1:
        raise DomainError("warehouse_operation_conflict", "仓库操作记录不唯一", status_code=409)
    operation = operations[0]
    if (
        operation.source_type != WAREHOUSE_SOURCE_PRODUCTION_POSITION
        or operation.production_item_id != production_item_id
    ):
        raise DomainError("warehouse_operation_conflict", "仓库操作业务上下文冲突", status_code=409)
    return operation


def _storage_response(operation) -> dict:
    return {
        "operation_group_no": operation.operation_group_no,
        "warehouse_stock_id": operation.warehouse_stock_id,
        "quantity": operation.quantity,
        "completion_status": operation.completion_status,
    }


__all__ = [
    "list_completed_plan_positions",
    "store_completed_plan_position",
]
