from sqlalchemy import func, select

from database import SessionLocal
from domain.time import business_now, utc_now
from domain.assembly import matches_assembly_sources, required_material_quantity
from models.engineering import ProductBom
from models.organization import Department, Worker
from models.production import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderMaterial,
)
from services.errors import DomainError
from services.production_movements import record_movement
from services.work_order_presenters import serialize_work_order
from services.work_order_support import (
    consume_repository,
    mark_order_planned,
    move_to_node,
    node_context,
    production_item_unit_quantity,
    refresh_order_closed,
    target_department_id,
)


def create_assembly_work_order(
    repository_ids: list[int],
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部门可以开装配工单", status_code=403)
    with SessionLocal.begin() as session:
        repositories = [
            session.get(Repository, repository_id, with_for_update=True)
            for repository_id in sorted(set(repository_ids))
        ]
        if len(repositories) < 2 or any(item is None for item in repositories):
            raise DomainError("assembly_inputs_invalid", "装配工单至少需要两个有效输入")
        input_items = [
            session.get(ProductionItem, repository.production_item_id)
            for repository in repositories
        ]
        order_item_ids = {item.customer_order_item_id for item in input_items}
        node_ids = {item.flow_node_id for item in repositories}
        if len(order_item_ids) != 1 or len(node_ids) != 1:
            raise DomainError("assembly_inputs_mismatch", "装配输入必须属于同一订单明细和装配节点")

        context, assembly_node = node_context(
            session, input_items[0], repositories[0].flow_node_id
        )
        if assembly_node.get("type") != "assembly":
            raise DomainError("assembly_node_invalid", "所选物料不在装配节点")
        expected_sources = [
            edge.get("source_node_id")
            for edge in context.flow.get("edges", [])
            if edge.get("target_node_id") == assembly_node["id"]
        ]
        selected_sources = [repository.source_flow_node_id for repository in repositories]
        if not matches_assembly_sources(expected_sources, selected_sources):
            raise DomainError("assembly_inputs_incomplete", "必须选择装配节点的全部输入物料")

        worker = session.get(Worker, worker_id) if worker_id else None
        assembly_department = session.scalar(
            select(Department).where(Department.department_code == "assembly")
        )
        if worker_id and (
            worker is None or worker.department_id != assembly_department.id
        ):
            raise DomainError("worker_invalid", "工人不属于装配部门")

        material_quantities = _allocate_materials(
            session, repositories, input_items, quantity
        )
        order = WorkOrder(
            repository_id=None,
            procedure_stage_stock_id=None,
            production_item_id=input_items[0].id,
            substep_id=None,
            work_order_type="assembly",
            work_order_name=(
                assembly_node.get("label")
                or assembly_node.get("output_name")
                or "装配"
            ),
            flow_node_id=assembly_node["id"],
            source_flow_node_id=None,
            worker_id=worker_id,
            quantity=quantity,
        )
        session.add(order)
        session.flush()
        mark_order_planned(session, input_items[0])
        order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
        for repository in repositories:
            material_quantity = material_quantities.get(repository.id)
            if material_quantity:
                session.add(
                    WorkOrderMaterial(
                        work_order_id=order.id,
                        repository_id=repository.id,
                        production_item_id=repository.production_item_id,
                        quantity=material_quantity,
                    )
                )
        session.flush()
        return serialize_work_order(session, order)


def _allocate_materials(
    session,
    repositories: list[Repository],
    input_items: list[ProductionItem],
    quantity: int,
) -> dict[int, int]:
    repositories_by_source: dict[str, list[tuple[Repository, ProductionItem]]] = {}
    for repository, input_item in zip(repositories, input_items, strict=True):
        repositories_by_source.setdefault(repository.source_flow_node_id, []).append(
            (repository, input_item)
        )

    allocated_quantities: dict[int, int] = {}
    for source_id, source_repositories in repositories_by_source.items():
        first_item = source_repositories[0][1]
        bom_item = (
            session.get(ProductBom, first_item.product_bom_id)
            if first_item.product_bom_id
            else None
        )
        remaining_required = required_material_quantity(
            quantity,
            production_item_unit_quantity(session, first_item, bom_item),
        )
        for repository, _ in source_repositories:
            reserved = session.scalar(
                select(func.coalesce(func.sum(WorkOrderMaterial.quantity), 0))
                .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
                .where(
                    WorkOrderMaterial.repository_id == repository.id,
                    WorkOrder.status == "open",
                )
            )
            allocated = min(max(repository.quantity - reserved, 0), remaining_required)
            if allocated:
                allocated_quantities[repository.id] = allocated
                remaining_required -= allocated
            if remaining_required == 0:
                break
        if remaining_required:
            raise DomainError(
                "assembly_quantity_exceeded",
                f"来源节点 {source_id} 的可用物料不足",
            )
    return allocated_quantities


def submit_assembly_work_order(
    session,
    order: WorkOrder,
    quantity: int,
    completion_action: str,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部门可以操作装配工单", status_code=403)
    if completion_action != "direct":
        raise DomainError("assembly_qc_not_supported", "装配工单当前仅支持直接结单")
    remaining = order.quantity - order.completed_quantity
    if quantity != remaining:
        raise DomainError("partial_completion_not_allowed", "装配工单必须一次完成剩余数量")

    input_item = session.get(ProductionItem, order.production_item_id, with_for_update=True)
    context, assembly_node = node_context(session, input_item, order.flow_node_id)
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all()
    for material in materials:
        if material.repository_id is None:
            raise DomainError("assembly_material_missing", "装配输入库存已不存在")
        repository = session.get(Repository, material.repository_id, with_for_update=True)
        if repository is None or repository.quantity < material.quantity:
            raise DomainError("assembly_material_insufficient", "装配输入库存不足")
        material_item = session.get(ProductionItem, material.production_item_id)
        record_movement(
            session,
            production_item=material_item,
            quantity=material.quantity,
            movement_type="assembly_input",
            source_flow_node_id=repository.flow_node_id,
            target_flow_node_id=None,
            source_department_id=repository.department_id,
            work_order_id=order.id,
        )
        if repository.quantity == material.quantity:
            material.repository_id = None
            # Release the composite repository reference before deleting an
            # exhausted repository row.
            session.flush()
        consume_repository(session, repository, material.quantity)

    output_item = ProductionItem(
        customer_order_item_id=context.order_item.id,
        product_id=context.order_item.product_id,
        product_version=context.order_item.product_version,
        product_bom_id=None,
        origin_flow_node_id=assembly_node["id"],
    )
    session.add(output_item)
    session.flush()
    order.production_item_id = output_item.id
    session.flush()
    target = context.normal_target(assembly_node["id"])
    output_quantity = quantity * int(assembly_node.get("output_pcs", 1))
    target_department = move_to_node(
        session, output_item, target, output_quantity, assembly_node["id"]
    )
    record_movement(
        session,
        production_item=output_item,
        quantity=output_quantity,
        movement_type="assembly_output",
        source_flow_node_id=assembly_node["id"],
        target_flow_node_id=target.get("id") if target else None,
        source_department_id=target_department_id(session, assembly_node),
        target_department_id=target_department,
        work_order_id=order.id,
    )
    # Persist the output while the assembly order is still open.
    session.flush()
    order.completed_quantity += quantity
    order.status = "closed"
    order.closed_at = utc_now()
    session.flush()
    refresh_order_closed(session, output_item)
    return serialize_work_order(session, order)
