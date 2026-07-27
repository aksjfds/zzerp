from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now
from domain.assembly import matches_assembly_sources, required_material_quantity
from modules.assembly.persistence import WorkOrderMaterial
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.assembly_api import (
    assembly_item_unit_quantity,
    assign_assembly_work_order_number,
    load_assembly_work_order,
    load_production_item,
    load_production_items,
    load_repositories,
    open_work_order_ids,
    record_assembly_output,
)
from modules.production_core.context_api import (
    InventorySourceContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import record_movement
from modules.production_core.operational_api import serialize_batch, serialize_work_order
from modules.production_core.operational_api import (
    order_remaining_quantity,
    rework_pending_quantities,
)
from modules.production_core.operational_api import process_qc_node
from modules.production_core.operational_api import (
    capture_operation_state,
    record_undoable_operation,
)
from modules.production_core.operational_api import (
    consume_repository,
    mark_order_planned,
    move_to_node,
    node_context,
    refresh_order_closed,
    target_department_id,
)
from modules.production_core.ownership_api import (
    create_assembly_work_order_record,
    create_production_item,
)
from modules.quality.ownership_api import create_inspection_batch
from modules.quality.inspection_api import (
    list_inspection_batches,
    load_inspection_batch,
)
from modules.workforce.reference_api import get_worker_reference


def create_assembly_work_order(
    repository_ids: list[int],
    quantity: int,
    worker_id: int | None,
    remark: str | None,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部门可以开装配工单", status_code=403)
    with SessionLocal.begin() as session:
        unique_repository_ids = sorted(set(repository_ids))
        repositories = load_repositories(
            session,
            unique_repository_ids,
            for_update=True,
        )
        if len(repositories) < 2 or len(repositories) != len(unique_repository_ids):
            raise DomainError("assembly_inputs_invalid", "装配工单至少需要两个有效输入")
        input_items_by_id = load_production_items(
            session,
            {repository.production_item_id for repository in repositories},
        )
        input_items = [
            input_items_by_id[repository.production_item_id]
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

        worker = get_worker_reference(session, worker_id) if worker_id else None
        assembly_department_id = get_department_ids_by_codes(
            session,
            {"assembly"},
        ).get("assembly")
        if worker_id and (
            worker is None or worker.department_id != assembly_department_id
        ):
            raise DomainError("worker_invalid", "工人不属于装配部门")

        material_quantities = _allocate_materials(
            session, repositories, input_items, quantity
        )
        order = create_assembly_work_order_record(
            session,
            production_item_id=input_items[0].id,
            flow_node_id=assembly_node["id"],
            work_order_name=(
                assembly_node.get("label")
                or assembly_node.get("output_name")
                or "装配"
            ),
            worker_id=worker_id,
            quantity=quantity,
            remark=remark,
        )
        mark_order_planned(session, input_items[0])
        assign_assembly_work_order_number(
            order,
            f"WO-{business_now():%Y%m%d}-{order.id:06d}",
        )
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
    repositories: list[InventorySourceContext],
    input_items: list[ProductionItemContext],
    quantity: int,
) -> dict[int, int]:
    repositories_by_source: dict[
        str,
        list[tuple[InventorySourceContext, ProductionItemContext]],
    ] = {}
    for repository, input_item in zip(repositories, input_items, strict=True):
        repositories_by_source.setdefault(repository.source_flow_node_id, []).append(
            (repository, input_item)
        )

    allocated_quantities: dict[int, int] = {}
    repository_ids = {repository.id for repository in repositories}
    material_rows = session.execute(
        select(
            WorkOrderMaterial.repository_id,
            WorkOrderMaterial.work_order_id,
            WorkOrderMaterial.quantity,
        ).where(WorkOrderMaterial.repository_id.in_(repository_ids))
    ).all()
    open_ids = open_work_order_ids(
        session,
        {row.work_order_id for row in material_rows},
    )
    reserved_by_repository: dict[int, int] = defaultdict(int)
    for row in material_rows:
        if row.repository_id is not None and row.work_order_id in open_ids:
            reserved_by_repository[row.repository_id] += row.quantity

    for source_id, source_repositories in repositories_by_source.items():
        first_item = source_repositories[0][1]
        remaining_required = required_material_quantity(
            quantity,
            assembly_item_unit_quantity(session, first_item),
        )
        for repository, _ in source_repositories:
            reserved = reserved_by_repository[repository.id]
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
    order: WorkOrderContext,
    quantity: int,
    completion_action: str,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部门可以操作装配工单", status_code=403)
    remaining = order_remaining_quantity(order)
    if quantity != remaining:
        raise DomainError("partial_completion_not_allowed", "装配工单必须一次完成剩余数量")

    input_item = load_production_item(
        session,
        order.production_item_id,
        for_update=True,
    )
    context, assembly_node = node_context(session, input_item, order.flow_node_id)
    qc_node = process_qc_node(context.flow, context.nodes, assembly_node["id"])
    if completion_action == "qc" and qc_node is None:
        raise DomainError("work_order_qc_not_configured", "装配节点后未配置QC节点")
    if completion_action == "direct" and qc_node is not None:
        raise DomainError("work_order_qc_required", "该装配节点必须送QC")
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all()
    for material in materials:
        if material.repository_id is None:
            raise DomainError("assembly_material_missing", "装配输入库存已不存在")
        repositories = load_repositories(
            session,
            {material.repository_id},
            for_update=True,
        )
        repository = repositories[0] if repositories else None
        if repository is None or repository.quantity < material.quantity:
            raise DomainError("assembly_material_insufficient", "装配输入库存不足")
        material_item = load_production_item(
            session,
            material.production_item_id,
        )
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

    output_item = create_production_item(
        session,
        customer_order_item_id=context.order_item.id,
        product_id=context.order_item.product_id,
        product_version=context.order_item.product_version,
        product_bom_id=None,
        origin_flow_node_id=assembly_node["id"],
    )
    record_assembly_output(
        order,
        production_item_id=output_item.id,
        completed_quantity=0,
        close_order=False,
    )
    session.flush()
    output_quantity = quantity * int(assembly_node.get("output_pcs", 1))
    if completion_action == "qc":
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=output_quantity,
            source_flow_node_id=assembly_node["id"],
        )
        record_movement(
            session,
            production_item=output_item,
            quantity=output_quantity,
            movement_type="assembly_output",
            source_flow_node_id=assembly_node["id"],
            target_flow_node_id=qc_node["id"],
            source_department_id=target_department_id(session, assembly_node),
            target_department_id=qc_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        record_assembly_output(
            order,
            production_item_id=output_item.id,
            completed_quantity=quantity,
            close_order=False,
        )
        session.flush()
        refresh_order_closed(session, output_item)
        return serialize_work_order(session, order)

    target = context.normal_target(assembly_node["id"])
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
    record_assembly_output(
        order,
        production_item_id=output_item.id,
        completed_quantity=quantity,
        close_order=True,
    )
    session.flush()
    refresh_order_closed(session, output_item)
    return serialize_work_order(session, order)


def resubmit_assembly_rework_batch(
    source_batch_id: int,
    quantity: int,
    user_department: str,
    actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        source_batch = load_inspection_batch(
            session,
            source_batch_id,
            for_update=True,
        )
        if source_batch is None:
            raise DomainError("qc_batch_not_found", "返工来源批次不存在", status_code=404)
        order = load_assembly_work_order(
            session,
            source_batch.work_order_id,
            for_update=True,
        )
        if order is None or order.work_order_type != "assembly":
            raise DomainError("qc_rework_order_invalid", "返工批次所属装配工单无效")
        if order.status != "open":
            raise DomainError("work_order_closed", "装配工单已经结单")
        before = capture_operation_state(session, order)
        if source_batch.recorded_at is None or source_batch.rework_quantity is None:
            raise DomainError("qc_batch_not_completed", "QC尚未录入返工结果")
        batches = list_inspection_batches(session, order.id)
        available = rework_pending_quantities(batches).get(source_batch.id, 0)
        if quantity <= 0 or quantity > available:
            raise DomainError("qc_rework_quantity_exceeded", "返工送检数量超过待返工数量")
        if user_department not in {"sys", "assembly"}:
            raise DomainError("department_access_denied", "只有装配部门可以提交返工送检", status_code=403)

        output_item = load_production_item(session, order.production_item_id)
        if output_item is None:
            raise DomainError("production_context_missing", "装配产出不存在")
        context, assembly_node = node_context(session, output_item, order.flow_node_id)
        qc_node = process_qc_node(context.flow, context.nodes, assembly_node["id"])
        if qc_node is None:
            raise DomainError("work_order_qc_not_configured", "装配节点后未配置QC节点")
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")

        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=quantity,
            source_flow_node_id=assembly_node["id"],
            rework_source_batch_id=source_batch.id,
        )
        record_movement(
            session,
            production_item=output_item,
            quantity=quantity,
            movement_type="assembly_output",
            source_flow_node_id=assembly_node["id"],
            target_flow_node_id=qc_node["id"],
            source_department_id=target_department_id(session, assembly_node),
            target_department_id=qc_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        record_undoable_operation(
            session,
            order,
            before,
            operation_type="rework_submission",
            operation_label="撤回返工送检",
            department_code="assembly",
            actor_username=actor_username,
        )
        return serialize_batch(batch, track_rework=True)
