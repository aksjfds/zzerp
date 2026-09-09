"""Read-only temporary warehouse stock and operation queries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.warehouse import (
    WAREHOUSE_CODE_AUXILIARY,
    WAREHOUSE_CODE_MAIN,
    WAREHOUSE_OPERATION_FAILED,
    WAREHOUSE_OPERATION_PENDING,
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_OPERATION_UNCERTAIN,
    WarehouseMaterialIdentity,
    WarehouseOperationSnapshot,
    WarehouseStockSnapshot,
)
from modules.errors import DomainError
from modules.inventory.persistence import WarehouseOperation
from modules.inventory.warehouse_contracts import WarehouseGatewayFactory
from modules.inventory.warehouse_gateway import PostgreSQLWarehouseGateway
from modules.inventory.warehouse_operation_support import _operation_snapshot


def list_warehouse_stocks(
    session: Session,
    *,
    item_code: str | None = None,
    product_version: int | None = None,
    item_type: str | None = None,
    warehouse_code: str | None = None,
    available_only: bool = False,
    gateway_factory: WarehouseGatewayFactory = PostgreSQLWarehouseGateway,
) -> tuple[WarehouseStockSnapshot, ...]:
    if item_code is not None and (
        not item_code or item_code.strip() != item_code
    ):
        raise DomainError("warehouse_item_code_invalid", "仓库品号不能为空或包含首尾空格")
    if product_version is not None and product_version <= 0:
        raise DomainError("warehouse_product_version_invalid", "产品版本必须大于0")
    if item_type is not None and item_type not in {"part", "assembly"}:
        raise DomainError("warehouse_item_type_invalid", "仓库物料类型无效")
    if warehouse_code is not None and warehouse_code not in {
        WAREHOUSE_CODE_MAIN,
        WAREHOUSE_CODE_AUXILIARY,
    }:
        raise DomainError("warehouse_code_invalid", "仓库代码无效")
    return gateway_factory(session).list_stocks(
        item_code=item_code,
        product_version=product_version,
        item_type=item_type,
        warehouse_code=warehouse_code,
        available_only=available_only,
    )


def list_warehouse_operations(
    session: Session,
    *,
    operation_group_no: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> tuple[WarehouseOperationSnapshot, ...]:
    if limit <= 0 or limit > 1000:
        raise DomainError("warehouse_operation_limit_invalid", "仓库操作记录条数必须在1到1000之间")
    statement = select(WarehouseOperation)
    if operation_group_no is not None:
        statement = statement.where(
            WarehouseOperation.operation_group_no == operation_group_no
        )
    if status is not None:
        if status not in {
            WAREHOUSE_OPERATION_PENDING,
            WAREHOUSE_OPERATION_SUCCEEDED,
            WAREHOUSE_OPERATION_FAILED,
            WAREHOUSE_OPERATION_UNCERTAIN,
        }:
            raise DomainError("warehouse_operation_status_invalid", "仓库操作状态无效")
        statement = statement.where(WarehouseOperation.status == status)
    statement = statement.order_by(
        WarehouseOperation.created_at.desc(),
        WarehouseOperation.id.desc(),
    ).limit(limit)
    return tuple(
        _operation_snapshot(operation)
        for operation in session.scalars(statement)
    )


def list_material_warehouse_stocks(
    session: Session,
    identities: tuple[WarehouseMaterialIdentity, ...],
    *,
    available_only: bool = False,
    gateway_factory: WarehouseGatewayFactory = PostgreSQLWarehouseGateway,
) -> tuple[WarehouseStockSnapshot, ...]:
    if any(
        not identity.item_code
        or identity.item_code.strip() != identity.item_code
        or identity.product_version <= 0
        or identity.item_type not in {"part", "assembly"}
        for identity in identities
    ):
        raise DomainError("warehouse_material_identity_invalid", "仓库物料身份无效")
    return gateway_factory(session).list_material_stocks(
        identities,
        available_only=available_only,
    )


def replayable_operation_group(session: Session, base_group_no: str) -> str:
    groups = list(session.scalars(
        select(WarehouseOperation.operation_group_no)
        .where(
            (WarehouseOperation.operation_group_no == base_group_no)
            | WarehouseOperation.operation_group_no.startswith(
                f"{base_group_no}:attempt:"
            )
        )
        .distinct()
    ))
    if not groups:
        return base_group_no

    def attempt_number(group_no: str) -> int:
        if group_no == base_group_no:
            return 1
        suffix = group_no.removeprefix(f"{base_group_no}:attempt:")
        return int(suffix) if suffix.isdigit() else 1

    latest_group = max(groups, key=attempt_number)
    original_ids = list(session.scalars(
        select(WarehouseOperation.id).where(
            WarehouseOperation.operation_group_no == latest_group
        )
    ))
    reversed_count = session.scalar(
        select(func.count(WarehouseOperation.id)).where(
            WarehouseOperation.reversal_of_operation_id.in_(original_ids)
        )
    ) or 0
    if reversed_count == 0:
        return latest_group
    if reversed_count != len(original_ids):
        raise DomainError(
            "warehouse_operation_reversal_incomplete",
            "仓库操作仅部分冲销，不能继续办理",
            status_code=409,
        )
    return f"{base_group_no}:attempt:{attempt_number(latest_group) + 1}"
