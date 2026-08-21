from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now
from domain.assembly import required_material_quantity
from modules.assembly.persistence import WorkOrderMaterial
from modules.errors import DomainError
from modules.organization.model_api import Workshop
from modules.organization.read_api import get_department_ids_by_codes
from modules.organization.transaction_api import resolve_workshop_procedure
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
from modules.production_core.model_api import ProductionItem
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
    ensure_production_plan_active,
    mark_order_planned,
    move_to_node,
    node_context,
    refresh_order_closed,
    target_department_id,
)
from modules.production_core.ownership_api import (
    add_repository_quantity,
    create_assembly_work_order_record,
    create_production_item,
)
from modules.production_core.flow import assembly_material_key
from modules.quality.ownership_api import create_inspection_batch
from modules.standard_execution.pricing_api import attach_work_order_price
from modules.standard_execution.procedures import material_key
from modules.quality.inspection_api import (
    list_inspection_batches,
    load_inspection_batch,
)
from modules.workforce.reference_api import get_worker_reference


def create_assembly_work_order(
    materials: list[dict],
    procedure_id: int | None,
    procedure_name: str | None,
    quantity: int,
    worker_id: int | None,
    remark: str | None,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部可以开装配工单", status_code=403)
    with SessionLocal.begin() as session:
        requested_quantities: dict[int, int] = {}
        for material in materials:
            repository_id = int(material["repository_id"])
            if repository_id in requested_quantities:
                raise DomainError("assembly_material_duplicate", "同一物料来源不能重复填写")
            requested_quantities[repository_id] = int(material["quantity"])
        unique_repository_ids = sorted(requested_quantities)
        repositories = load_repositories(
            session,
            unique_repository_ids,
            for_update=True,
        )
        if not repositories or len(repositories) != len(unique_repository_ids):
            raise DomainError("assembly_inputs_invalid", "请选择有效的工单输入物料")
        input_items_by_id = load_production_items(
            session,
            {repository.production_item_id for repository in repositories},
        )
        input_items = [
            input_items_by_id[repository.production_item_id]
            for repository in repositories
        ]
        ensure_production_plan_active(session, input_items[0])
        order_item_ids = {item.customer_order_item_id for item in input_items}
        node_ids = {item.flow_node_id for item in repositories}
        if len(order_item_ids) != 1 or len(node_ids) != 1:
            raise DomainError("assembly_inputs_mismatch", "多路工艺输入必须属于同一订单明细和工艺节点")

        context, assembly_node = node_context(
            session, input_items[0], repositories[0].flow_node_id
        )
        if assembly_node.get("type") != "assembly":
            raise DomainError("assembly_node_invalid", "所选物料不在多路工艺节点")
        workshop_id = assembly_node.get("workshop_id")
        if not isinstance(workshop_id, int):
            raise DomainError("assembly_workshop_invalid", "多路节点未配置车间")
        procedure = resolve_workshop_procedure(
            session,
            workshop_id=workshop_id,
            procedure_id=procedure_id,
            procedure_name=procedure_name,
            input_mode="multiple",
        )
        continuation = (
            len(repositories) == 1
            and input_items[0].product_bom_id is None
            and input_items[0].origin_flow_node_id == assembly_node["id"]
        )
        expected_sources = [
            edge.get("source_node_id")
            for edge in context.flow.get("edges", [])
            if edge.get("target_node_id") == assembly_node["id"]
        ]
        expected_materials = {
            key
            for source_id in expected_sources
            if (key := assembly_material_key(context.flow, context.nodes, source_id))
        }
        selected_materials = {
            _production_item_material_key(item) for item in input_items
        }
        if not continuation and (not expected_materials or expected_materials != selected_materials):
            raise DomainError("assembly_inputs_incomplete", "必须填写多路工艺节点的全部输入物料")

        assembly_department_id = get_department_ids_by_codes(
            session,
            {"assembly"},
        ).get("assembly")
        worker = get_worker_reference(session, worker_id) if worker_id else None
        workshop = session.get(Workshop, procedure.workshop_id)
        if workshop is None or workshop.department_id != assembly_department_id:
            raise DomainError("assembly_procedure_invalid", "多路工艺不属于装配部")
        if worker_id and (
            worker is None
            or worker.department_id != assembly_department_id
            or worker.workshop_id != procedure.workshop_id
        ):
            raise DomainError("worker_invalid", "工人不属于当前装配工艺车间")

        if continuation:
            if requested_quantities[repositories[0].id] != quantity or quantity > repositories[0].quantity:
                raise DomainError("assembly_quantity_exceeded", "后续工艺数量必须等于所选在制数量")
            material_quantities = {repositories[0].id: quantity}
        else:
            material_quantities = _validate_material_allocations(
                session,
                repositories,
                input_items,
                requested_quantities,
                quantity,
            )
        output_item = _get_or_create_output_item(
            session,
            customer_order_item_id=input_items[0].customer_order_item_id,
            product_id=input_items[0].product_id,
            product_version=input_items[0].product_version,
            assembly_node_id=assembly_node["id"],
        )
        order = create_assembly_work_order_record(
            session,
            production_item_id=output_item.id,
            procedure_id=procedure.id,
            flow_node_id=assembly_node["id"],
            work_order_name=procedure.procedure_name,
            worker_id=worker_id,
            quantity=quantity,
            remark=remark,
            repository_id=repositories[0].id if continuation else None,
        )
        mark_order_planned(session, input_items[0])
        assign_assembly_work_order_number(
            order,
            f"WO-{business_now():%Y%m%d}-{order.id:06d}",
        )
        attach_work_order_price(
            session,
            work_order_id=order.id,
            product_id=output_item.product_id,
            product_version=output_item.product_version,
            material_key=material_key(output_item),
            flow_node_id=assembly_node["id"],
            procedure_id=procedure.id,
            procedure_name=procedure.procedure_name,
        )
        if continuation:
            session.flush()
            return serialize_work_order(session, order)
        for repository, input_item in zip(repositories, input_items, strict=True):
            material_quantity = material_quantities.get(repository.id)
            if material_quantity:
                material_row = WorkOrderMaterial(
                    work_order_id=order.id,
                    repository_id=repository.id,
                    production_item_id=repository.production_item_id,
                    quantity=material_quantity,
                    source_flow_node_id=repository.flow_node_id,
                    source_previous_flow_node_id=repository.source_flow_node_id,
                    source_department_id=repository.department_id,
                    source_work_order_id=repository.source_work_order_id,
                )
                session.add(material_row)
                record_movement(
                    session,
                    production_item=input_item,
                    quantity=material_quantity,
                    movement_type="assembly_input",
                    source_flow_node_id=repository.flow_node_id,
                    target_flow_node_id=None,
                    source_department_id=repository.department_id,
                    work_order_id=order.id,
                )
                if repository.quantity == material_quantity:
                    material_row.repository_id = None
                    session.flush()
                consume_repository(session, repository, material_quantity)
        session.flush()
        return serialize_work_order(session, order)


def _validate_material_allocations(
    session,
    repositories: list[InventorySourceContext],
    input_items: list[ProductionItemContext],
    requested_quantities: dict[int, int],
    quantity: int,
) -> dict[int, int]:
    repositories_by_source: dict[
        str,
        list[tuple[InventorySourceContext, ProductionItemContext]],
    ] = {}
    for repository, input_item in zip(repositories, input_items, strict=True):
        repositories_by_source.setdefault(_production_item_material_key(input_item), []).append(
            (repository, input_item)
        )

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

    for material_key, source_repositories in repositories_by_source.items():
        first_item = source_repositories[0][1]
        required_quantity = required_material_quantity(
            quantity,
            assembly_item_unit_quantity(session, first_item),
        )
        selected_quantity = sum(
            requested_quantities[repository.id]
            for repository, _ in source_repositories
        )
        if selected_quantity != required_quantity:
            raise DomainError(
                "assembly_material_quantity_mismatch",
                f"同一物料的来源数量合计必须为 {required_quantity}",
            )
        for repository, _ in source_repositories:
            reserved = reserved_by_repository[repository.id]
            if requested_quantities[repository.id] > max(repository.quantity - reserved, 0):
                raise DomainError(
                    "assembly_quantity_exceeded",
                    "所填来源数量超过当前可用数量",
                )
    return {
        repository_id: material_quantity
        for repository_id, material_quantity in requested_quantities.items()
        if material_quantity > 0
    }


def _production_item_material_key(item: ProductionItemContext) -> str:
    if item.product_bom_id is not None:
        return f"part:{item.product_bom_id}"
    return f"assembly:{item.origin_flow_node_id}"


def _get_or_create_output_item(
    session,
    *,
    customer_order_item_id: int,
    product_id: int,
    product_version: int,
    assembly_node_id: str,
):
    output_item = session.scalar(
        select(ProductionItem)
        .where(
            ProductionItem.customer_order_item_id == customer_order_item_id,
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.product_bom_id.is_(None),
            ProductionItem.origin_flow_node_id == assembly_node_id,
        )
        .with_for_update()
    )
    if output_item is not None:
        return output_item
    return create_production_item(
        session,
        customer_order_item_id=customer_order_item_id,
        product_id=product_id,
        product_version=product_version,
        product_bom_id=None,
        origin_flow_node_id=assembly_node_id,
    )


def submit_assembly_work_order(
    session,
    order: WorkOrderContext,
    quantity: int,
    completion_action: str,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "assembly"}:
        raise DomainError(
            "department_access_denied",
            "只有装配部可以操作装配工单",
            status_code=403,
        )
    remaining = order_remaining_quantity(order)
    if quantity != remaining:
        raise DomainError("assembly_submission_must_be_full", "装配工单必须整单提交")

    input_item = load_production_item(
        session,
        order.production_item_id,
        for_update=True,
    )
    context, assembly_node = node_context(session, input_item, order.flow_node_id)
    qc_node = process_qc_node(context.flow, context.nodes, assembly_node["id"])
    if completion_action == "qc" and qc_node is None:
        raise DomainError("work_order_qc_not_configured", "装配节点后未配置QC节点")
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all()
    output_item = input_item
    output_quantity = quantity * (
        int(assembly_node.get("output_pcs", 1)) if materials else 1
    )
    if not materials:
        repositories = load_repositories(
            session,
            {order.repository_id} if order.repository_id else set(),
            for_update=True,
        )
        source = repositories[0] if repositories else None
        if source is None or source.quantity < quantity:
            raise DomainError("assembly_material_insufficient", "当前在制装配体数量不足")
        if source.quantity == quantity:
            order.repository_id = None
            session.flush()
        consume_repository(session, source, quantity)
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
            completed_quantity=quantity,
            close_order=False,
        )
        session.flush()
        refresh_order_closed(session, output_item)
        return serialize_work_order(session, order)

    assembly_department = target_department_id(session, assembly_node)
    add_repository_quantity(
        session,
        production_item_id=output_item.id,
        flow_node_id=assembly_node["id"],
        source_flow_node_id=assembly_node["id"],
        department_id=assembly_department,
        quantity=output_quantity,
        source_work_order_id=order.id,
    )
    record_movement(
        session,
        production_item=output_item,
        quantity=output_quantity,
        movement_type="assembly_output",
        source_flow_node_id=assembly_node["id"],
        target_flow_node_id=assembly_node["id"],
        source_department_id=assembly_department,
        target_department_id=assembly_department,
        work_order_id=order.id,
    )
    # Persist the output while the assembly order is still open.
    session.flush()
    record_assembly_output(
        order,
        completed_quantity=quantity,
        close_order=order.completed_quantity + quantity >= order.quantity,
    )
    session.flush()
    refresh_order_closed(session, output_item)
    return serialize_work_order(session, order)


def restore_cancelled_assembly_materials(session, order: WorkOrderContext) -> None:
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .with_for_update()
    ).all()
    for material in materials:
        production_item = load_production_item(
            session,
            material.production_item_id,
            for_update=True,
        )
        if production_item is None:
            raise DomainError("assembly_material_missing", "装配工单原配件不存在")
        repository = add_repository_quantity(
            session,
            production_item_id=material.production_item_id,
            flow_node_id=material.source_flow_node_id,
            source_flow_node_id=material.source_previous_flow_node_id,
            department_id=material.source_department_id,
            quantity=material.quantity,
            source_work_order_id=material.source_work_order_id,
        )
        material.repository_id = repository.id if repository else None
        record_movement(
            session,
            production_item=production_item,
            quantity=material.quantity,
            movement_type="assembly_input_restore",
            source_flow_node_id=material.source_flow_node_id,
            target_flow_node_id=material.source_flow_node_id,
            source_department_id=material.source_department_id,
            target_department_id=material.source_department_id,
            work_order_id=order.id,
        )


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
        if available <= 0 or quantity != available:
            raise DomainError(
                "qc_rework_full_quantity_required",
                "返工送检必须一次提交该批全部待返工数量",
            )
        if user_department not in {"sys", "assembly"}:
            raise DomainError("department_access_denied", "只有装配部可以提交返工送检", status_code=403)

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
