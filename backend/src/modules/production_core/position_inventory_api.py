"""Production-owner API for storing unprocessed current-position material."""

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.warehouse import WarehouseItemType
from modules.engineering.model_api import Product, ProductBom
from modules.errors import DomainError
from modules.production_core.card_status import reserved_quantities
from modules.production_core.flow_api import (
    ProductionFlowContext,
    load_production_flow,
    material_completion_status,
)
from modules.production_core.movements import record_movement
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
)
from modules.production_core.work_order_support import consume_repository
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


@dataclass(frozen=True, slots=True)
class ProductionPositionCandidate:
    production_item_id: int
    customer_order_item_id: int
    customer_order_no: str
    product_code: str
    product_name: str
    product_version: int
    item_type: WarehouseItemType
    item_code: str
    item_name: str
    department_code: str
    flow_node_id: str
    source_flow_node_id: str
    current_node_label: str
    completed_flow_node_id: str
    completion_status: str
    available_quantity: int
    position_version: str


@dataclass(frozen=True, slots=True)
class LockedProductionPosition:
    candidate: ProductionPositionCandidate
    production_item: ProductionItem
    repositories: tuple[Repository, ...]
    reserved_by_repository: dict[int, int]


def list_available_production_positions(
    session: Session,
    *,
    department_id: int,
    department_code: str,
    completed_order_item_ids: set[int],
) -> tuple[ProductionPositionCandidate, ...]:
    if not completed_order_item_ids:
        return ()
    repositories = list(session.scalars(
        select(Repository)
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .where(
            Repository.department_id == department_id,
            ProductionItem.customer_order_item_id.in_(completed_order_item_ids),
        )
        .order_by(
            Repository.production_item_id,
            Repository.flow_node_id,
            Repository.source_flow_node_id,
            Repository.id,
        )
    ))
    return _group_positions(session, department_code, repositories)


def department_position_order_item_ids(
    session: Session,
    department_id: int,
) -> set[int]:
    return set(session.scalars(
        select(ProductionItem.customer_order_item_id)
        .join(Repository, Repository.production_item_id == ProductionItem.id)
        .where(Repository.department_id == department_id)
        .distinct()
    ))


def get_available_production_position(
    session: Session,
    *,
    department_id: int,
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
) -> ProductionPositionCandidate | None:
    repositories = list(session.scalars(
        select(Repository)
        .where(
            Repository.production_item_id == production_item_id,
            Repository.flow_node_id == flow_node_id,
            Repository.source_flow_node_id == source_flow_node_id,
            Repository.department_id == department_id,
        )
        .order_by(Repository.id)
    ))
    candidates = _group_positions(session, department_code, repositories)
    return candidates[0] if candidates else None


def position_inventory_movement_matches(
    session: Session,
    *,
    warehouse_operation_id: int,
    production_item_id: int,
) -> bool:
    return session.scalar(
        select(ProductionMovement.id).where(
            ProductionMovement.warehouse_operation_id == warehouse_operation_id,
            ProductionMovement.production_item_id == production_item_id,
            ProductionMovement.movement_type == "production_inventory",
        )
    ) is not None


def lock_production_position(
    session: Session,
    *,
    department_id: int,
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    position_version: str,
    quantity: int,
) -> LockedProductionPosition:
    if quantity <= 0:
        raise DomainError("warehouse_storage_quantity_invalid", "入库数量必须大于0")
    repositories = tuple(session.scalars(
        select(Repository)
        .where(
            Repository.production_item_id == production_item_id,
            Repository.flow_node_id == flow_node_id,
            Repository.source_flow_node_id == source_flow_node_id,
            Repository.department_id == department_id,
        )
        .order_by(Repository.id)
        .with_for_update()
    ))
    if not repositories:
        raise DomainError("warehouse_storage_source_missing", "当前生产位置不存在", status_code=404)
    production_item = session.get(ProductionItem, production_item_id)
    if production_item is None:
        raise DomainError("warehouse_storage_source_missing", "当前生产位置不存在", status_code=404)
    candidates = _group_positions(session, department_code, list(repositories))
    candidate = candidates[0] if candidates else None
    if candidate is None:
        raise DomainError("warehouse_storage_source_empty", "当前生产位置没有可入库数量", status_code=409)
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
    reserved = reserved_quantities(session, [item.id for item in repositories])
    return LockedProductionPosition(
        candidate=candidate,
        production_item=production_item,
        repositories=repositories,
        reserved_by_repository=reserved,
    )


def consume_position_for_warehouse(
    session: Session,
    locked: LockedProductionPosition,
    *,
    quantity: int,
    warehouse_department_id: int,
    warehouse_operation_id: int,
) -> None:
    remaining = quantity
    for repository in locked.repositories:
        available = max(
            repository.quantity - locked.reserved_by_repository.get(repository.id, 0),
            0,
        )
        allocated = min(available, remaining)
        if allocated:
            consume_repository(session, repository, allocated)
            remaining -= allocated
        if not remaining:
            break
    if remaining:
        raise DomainError(
            "warehouse_storage_quantity_changed",
            "当前生产位置数量已变化，请刷新后重试",
            status_code=409,
        )
    record_movement(
        session,
        production_item=locked.production_item,
        quantity=quantity,
        movement_type="production_inventory",
        source_flow_node_id=locked.candidate.flow_node_id,
        target_flow_node_id=None,
        source_department_id=locked.repositories[0].department_id,
        target_department_id=warehouse_department_id,
        warehouse_operation_id=warehouse_operation_id,
    )


def _group_positions(
    session: Session,
    department_code: str,
    repositories: list[Repository],
) -> tuple[ProductionPositionCandidate, ...]:
    grouped: dict[tuple[int, str, str], list[Repository]] = {}
    for repository in repositories:
        grouped.setdefault(
            (
                repository.production_item_id,
                repository.flow_node_id,
                repository.source_flow_node_id,
            ),
            [],
        ).append(repository)
    all_ids = [repository.id for repository in repositories]
    reserved = reserved_quantities(session, all_ids)
    candidates = []
    for rows in grouped.values():
        available = sum(
            max(row.quantity - reserved.get(row.id, 0), 0)
            for row in rows
        )
        if available <= 0:
            continue
        candidate = _position_candidate(
            session,
            department_code,
            rows,
            reserved,
            available,
        )
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _position_candidate(
    session: Session,
    department_code: str,
    repositories: list[Repository],
    reserved: dict[int, int],
    available: int,
) -> ProductionPositionCandidate | None:
    repository = repositories[0]
    production_item = session.get(ProductionItem, repository.production_item_id)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在", status_code=409)
    if repository.source_flow_node_id == repository.flow_node_id:
        return None
    context = load_production_flow(session, production_item)
    origin_node = context.nodes.get(production_item.origin_flow_node_id)
    if (
        repository.source_flow_node_id == production_item.origin_flow_node_id
        and origin_node is not None
        and origin_node.get("type") == "part"
    ):
        return None
    current_node = context.nodes.get(repository.flow_node_id)
    if current_node is None or current_node.get("type") not in {"process", "assembly"}:
        raise DomainError("warehouse_storage_node_invalid", "当前流程节点不能直接入库", status_code=409)
    completed = material_completion_status(
        context.flow,
        context.nodes,
        production_item.origin_flow_node_id,
        repository.source_flow_node_id,
    )
    item_type, item_code, item_name = _material_identity(
        session,
        production_item,
        context,
    )
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = (
        session.get(CustomerOrder, order_item.customer_order_id)
        if order_item is not None
        else None
    )
    product = session.get(Product, production_item.product_id)
    if order_item is None or customer_order is None or product is None:
        raise DomainError("production_context_missing", "生产位置业务资料不完整", status_code=409)
    return ProductionPositionCandidate(
        production_item_id=production_item.id,
        customer_order_item_id=production_item.customer_order_item_id,
        customer_order_no=customer_order.customer_order_no,
        product_code=product.factory_code,
        product_name=product.product_name,
        product_version=production_item.product_version,
        item_type=item_type,
        item_code=item_code,
        item_name=item_name,
        department_code=department_code,
        flow_node_id=repository.flow_node_id,
        source_flow_node_id=repository.source_flow_node_id,
        current_node_label=str(current_node.get("label") or repository.flow_node_id),
        completed_flow_node_id=completed.flow_node_id,
        completion_status=completed.completion_status,
        available_quantity=available,
        position_version=_position_version(repositories, reserved),
    )


def _material_identity(
    session: Session,
    production_item: ProductionItem,
    context: ProductionFlowContext,
) -> tuple[WarehouseItemType, str, str]:
    if production_item.product_bom_id is not None:
        bom = session.get(ProductBom, production_item.product_bom_id)
        if bom is None:
            raise DomainError("warehouse_storage_item_invalid", "配件资料不存在", status_code=409)
        return "part", bom.part_no, bom.part_name
    origin = context.nodes.get(production_item.origin_flow_node_id, {})
    code = str(origin.get("assembly_code") or "").strip()
    name = str(origin.get("assembly_name") or origin.get("output_name") or "").strip()
    if not code or not name:
        raise DomainError("warehouse_storage_item_invalid", "装配体编号或名称不完整", status_code=409)
    return "assembly", code, name


def _position_version(
    repositories: list[Repository],
    reserved: dict[int, int],
) -> str:
    snapshot = "|".join(
        f"{row.id}:{row.quantity}:{reserved.get(row.id, 0)}"
        for row in repositories
    )
    return sha256(snapshot.encode("utf-8")).hexdigest()


__all__ = [
    "LockedProductionPosition",
    "ProductionPositionCandidate",
    "consume_position_for_warehouse",
    "department_position_order_item_ids",
    "get_available_production_position",
    "list_available_production_positions",
    "lock_production_position",
    "position_inventory_movement_matches",
]
