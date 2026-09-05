"""Production-owned current-material query and position-storage API."""

from dataclasses import dataclass, replace
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.warehouse import WarehouseItemType
from modules.engineering.model_api import Product, ProductBom
from modules.errors import DomainError
from modules.production_core.work_order_status import reserved_quantities
from modules.production_core.flow_api import (
    ProductionFlowContext,
    load_production_flow,
)
from modules.production_core.material_state_api import get_material_state
from modules.production_core.movements import record_movement
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    ProductionWarehouseStorageLine,
    Repository,
    WorkOrder,
    WorkOrderMaterial,
)
from modules.production_core.work_order_support import consume_repository
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


@dataclass(frozen=True, slots=True)
class DepartmentMaterialPosition:
    production_item_id: int
    processing_state_id: int
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
    resume_flow_node_id: str
    procedure_history: tuple[dict, ...]
    qc_status: str
    processing_status: str
    on_hand_quantity: int
    occupied_quantity: int
    available_quantity: int
    position_version: str


@dataclass(frozen=True, slots=True)
class LockedProductionPosition:
    candidate: DepartmentMaterialPosition
    production_item: ProductionItem
    repositories: tuple[Repository, ...]
    reserved_by_repository: dict[int, int]


def list_department_material_positions(
    session: Session,
    *,
    department_id: int,
    department_code: str,
) -> tuple[DepartmentMaterialPosition, ...]:
    repositories = list(session.scalars(
        select(Repository)
        .where(
            Repository.department_id == department_id,
        )
        .order_by(
            Repository.production_item_id,
            Repository.flow_node_id,
            Repository.source_flow_node_id,
            Repository.id,
        )
    ))
    repository_positions = _group_positions(session, department_code, repositories)
    occupied_assembly_positions = _occupied_assembly_positions(
        session,
        department_id=department_id,
        department_code=department_code,
    )
    return _merge_material_positions(
        repository_positions,
        occupied_assembly_positions,
    )


def get_department_material_position(
    session: Session,
    *,
    department_id: int,
    department_code: str,
    production_item_id: int,
    processing_state_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
) -> DepartmentMaterialPosition | None:
    repositories = list(session.scalars(
        select(Repository)
        .where(
            Repository.production_item_id == production_item_id,
            Repository.processing_state_id == processing_state_id,
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
    processing_state_id: int,
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
            Repository.processing_state_id == processing_state_id,
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
            session.add(ProductionWarehouseStorageLine(
                warehouse_operation_id=warehouse_operation_id,
                original_repository_id=repository.id,
                production_item_id=repository.production_item_id,
                processing_state_id=repository.processing_state_id,
                flow_node_id=repository.flow_node_id,
                source_flow_node_id=repository.source_flow_node_id,
                department_id=repository.department_id,
                source_work_order_id=repository.source_work_order_id,
                quantity=allocated,
            ))
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


def restore_position_from_warehouse(
    session: Session,
    *,
    original_warehouse_operation_id: int,
    reversal_warehouse_operation_id: int,
) -> None:
    lines = list(session.scalars(
        select(ProductionWarehouseStorageLine)
        .where(
            ProductionWarehouseStorageLine.warehouse_operation_id
            == original_warehouse_operation_id
        )
        .order_by(ProductionWarehouseStorageLine.id)
        .with_for_update()
    ))
    if not lines:
        raise DomainError("warehouse_storage_snapshot_missing", "原生产仓位明细不存在", status_code=409)
    original_movement = session.scalar(
        select(ProductionMovement)
        .where(
            ProductionMovement.warehouse_operation_id == original_warehouse_operation_id,
            ProductionMovement.movement_type == "production_inventory",
        )
        .with_for_update()
    )
    if original_movement is None:
        raise DomainError("warehouse_storage_movement_missing", "原生产入仓流水不存在", status_code=409)
    existing_restore = session.scalar(
        select(ProductionMovement.id).where(
            ProductionMovement.warehouse_operation_id == reversal_warehouse_operation_id,
            ProductionMovement.movement_type == "production_inventory_restore",
        )
    )
    if existing_restore is not None:
        return
    later_movement = session.scalar(
        select(ProductionMovement.id)
        .where(
            ProductionMovement.production_item_id == original_movement.production_item_id,
            ProductionMovement.id > original_movement.id,
        )
        .limit(1)
    )
    if later_movement is not None:
        raise DomainError(
            "warehouse_storage_has_downstream_changes",
            "该物料入仓后已经发生其他生产流转，不能冲销",
            status_code=409,
        )
    production_item = session.get(
        ProductionItem,
        original_movement.production_item_id,
        with_for_update=True,
    )
    if production_item is None:
        raise DomainError("production_context_missing", "原生产物料不存在", status_code=409)
    for line in lines:
        repository = session.scalar(
            select(Repository)
            .where(
                Repository.production_item_id == line.production_item_id,
                Repository.processing_state_id == line.processing_state_id,
                Repository.flow_node_id == line.flow_node_id,
                Repository.source_flow_node_id == line.source_flow_node_id,
                Repository.department_id == line.department_id,
                Repository.source_work_order_id == line.source_work_order_id,
            )
            .with_for_update()
        )
        if repository is None:
            repository = Repository(
                production_item_id=line.production_item_id,
                processing_state_id=line.processing_state_id,
                flow_node_id=line.flow_node_id,
                source_flow_node_id=line.source_flow_node_id,
                department_id=line.department_id,
                source_work_order_id=line.source_work_order_id,
                quantity=0,
            )
            session.add(repository)
        repository.quantity += line.quantity
    record_movement(
        session,
        production_item=production_item,
        quantity=sum(line.quantity for line in lines),
        movement_type="production_inventory_restore",
        source_flow_node_id=original_movement.source_flow_node_id,
        target_flow_node_id=original_movement.source_flow_node_id,
        source_department_id=original_movement.target_department_id,
        target_department_id=original_movement.source_department_id,
        warehouse_operation_id=reversal_warehouse_operation_id,
    )
    session.flush()


def _group_positions(
    session: Session,
    department_code: str,
    repositories: list[Repository],
) -> tuple[DepartmentMaterialPosition, ...]:
    grouped: dict[tuple[int, int, str, str], list[Repository]] = {}
    for repository in repositories:
        grouped.setdefault(
            (
                repository.production_item_id,
                repository.processing_state_id,
                repository.flow_node_id,
                repository.source_flow_node_id,
            ),
            [],
        ).append(repository)
    all_ids = [repository.id for repository in repositories]
    reserved = reserved_quantities(session, all_ids)
    candidates = []
    for rows in grouped.values():
        on_hand = sum(row.quantity for row in rows)
        occupied = sum(
            min(reserved.get(row.id, 0), row.quantity)
            for row in rows
        )
        available = sum(
            max(row.quantity - reserved.get(row.id, 0), 0)
            for row in rows
        )
        candidate = _position_candidate(
            session,
            department_code,
            rows,
            reserved,
            on_hand,
            occupied,
            available,
        )
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _occupied_assembly_positions(
    session: Session,
    *,
    department_id: int,
    department_code: str,
) -> tuple[DepartmentMaterialPosition, ...]:
    rows = list(session.execute(
        select(WorkOrderMaterial, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
        .where(
            WorkOrderMaterial.source_department_id == department_id,
            WorkOrderMaterial.repository_id.is_(None),
            WorkOrder.work_order_type == "assembly",
            WorkOrder.repository_id.is_(None),
            WorkOrder.status == "open",
            WorkOrder.processed_quantity == 0,
        )
        .order_by(WorkOrderMaterial.id)
    ))
    grouped: dict[
        tuple[int, int, str, str],
        list[tuple[WorkOrderMaterial, WorkOrder]],
    ] = {}
    for material, order in rows:
        grouped.setdefault(
            (
                material.production_item_id,
                material.source_processing_state_id,
                material.source_flow_node_id,
                material.source_previous_flow_node_id,
            ),
            [],
        ).append((material, order))
    return tuple(
        _occupied_assembly_candidate(
            session,
            department_code,
            allocations,
        )
        for allocations in grouped.values()
    )


def _occupied_assembly_candidate(
    session: Session,
    department_code: str,
    allocations: list[tuple[WorkOrderMaterial, WorkOrder]],
) -> DepartmentMaterialPosition:
    material = allocations[0][0]
    production_item = session.get(ProductionItem, material.production_item_id)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在", status_code=409)
    context = load_production_flow(session, production_item)
    current_node = context.nodes.get(material.source_flow_node_id)
    if current_node is None or current_node.get("type") != "assembly":
        raise DomainError("production_context_missing", "装配工单投入节点不存在", status_code=409)
    processing_state = get_material_state(session, material.source_processing_state_id)
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
    occupied = sum(item.quantity for item, _ in allocations)
    snapshot = "|".join(
        f"{item.id}:{order.id}:{item.quantity}"
        for item, order in allocations
    )
    return DepartmentMaterialPosition(
        production_item_id=production_item.id,
        processing_state_id=processing_state.id,
        customer_order_item_id=production_item.customer_order_item_id,
        customer_order_no=customer_order.customer_order_no,
        product_code=product.factory_code,
        product_name=product.product_name,
        product_version=production_item.product_version,
        item_type=item_type,
        item_code=item_code,
        item_name=item_name,
        department_code=department_code,
        flow_node_id=material.source_flow_node_id,
        source_flow_node_id=material.source_previous_flow_node_id,
        current_node_label=str(current_node.get("label") or material.source_flow_node_id),
        completed_flow_node_id=processing_state.completed_flow_node_id,
        resume_flow_node_id=processing_state.resume_flow_node_id,
        procedure_history=processing_state.procedure_history,
        qc_status=processing_state.qc_status,
        processing_status=processing_state.display_text,
        on_hand_quantity=occupied,
        occupied_quantity=occupied,
        available_quantity=0,
        position_version=sha256(snapshot.encode("utf-8")).hexdigest(),
    )


def _merge_material_positions(
    repository_positions: tuple[DepartmentMaterialPosition, ...],
    occupied_positions: tuple[DepartmentMaterialPosition, ...],
) -> tuple[DepartmentMaterialPosition, ...]:
    positions = {
        _material_position_key(position): position
        for position in repository_positions
    }
    for occupied in occupied_positions:
        key = _material_position_key(occupied)
        current = positions.get(key)
        if current is None:
            positions[key] = occupied
            continue
        positions[key] = replace(
            current,
            on_hand_quantity=current.on_hand_quantity + occupied.on_hand_quantity,
            occupied_quantity=current.occupied_quantity + occupied.occupied_quantity,
        )
    return tuple(positions.values())


def _material_position_key(
    position: DepartmentMaterialPosition,
) -> tuple[int, int, str, str]:
    return (
        position.production_item_id,
        position.processing_state_id,
        position.flow_node_id,
        position.source_flow_node_id,
    )


def _position_candidate(
    session: Session,
    department_code: str,
    repositories: list[Repository],
    reserved: dict[int, int],
    on_hand: int,
    occupied: int,
    available: int,
) -> DepartmentMaterialPosition | None:
    repository = repositories[0]
    production_item = session.get(ProductionItem, repository.production_item_id)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在", status_code=409)
    context = load_production_flow(session, production_item)
    current_node = context.nodes.get(repository.flow_node_id)
    if current_node is None or current_node.get("type") not in {"process", "assembly"}:
        raise DomainError("warehouse_storage_node_invalid", "当前流程节点不能直接入库", status_code=409)
    processing_state = get_material_state(session, repository.processing_state_id)
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
    return DepartmentMaterialPosition(
        production_item_id=production_item.id,
        processing_state_id=processing_state.id,
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
        completed_flow_node_id=processing_state.completed_flow_node_id,
        resume_flow_node_id=processing_state.resume_flow_node_id,
        procedure_history=processing_state.procedure_history,
        qc_status=processing_state.qc_status,
        processing_status=processing_state.display_text,
        on_hand_quantity=on_hand,
        occupied_quantity=occupied,
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
        f"{row.id}:{row.processing_state_id}:{row.quantity}:{reserved.get(row.id, 0)}"
        for row in repositories
    )
    return sha256(snapshot.encode("utf-8")).hexdigest()


__all__ = [
    "LockedProductionPosition",
    "DepartmentMaterialPosition",
    "consume_position_for_warehouse",
    "get_department_material_position",
    "list_department_material_positions",
    "lock_production_position",
    "position_inventory_movement_matches",
    "restore_position_from_warehouse",
]
