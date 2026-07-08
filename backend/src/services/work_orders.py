from datetime import datetime

from sqlalchemy import exists, func, or_, select

from database import SessionLocal
from domain.assembly import matches_assembly_sources, required_material_quantity
from services.production_flow import load_production_flow, normal_target
from models.engineering import ProductBom
from models.organization import Department, Procedure, Worker, Workshop
from models.production import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
    WorkOrderMaterial,
)
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError
from services.work_order_presenters import (
    item_display as _item_display,
    qc_repository_id as _qc_repository_id,
    serialize_batch as _serialize_batch,
    serialize_work_order as _serialize_work_order,
    work_order_context as _work_order_context,
)
from services.production_movements import record_movement


def _item_context(session, production_item: ProductionItem):
    context = load_production_flow(session, production_item)
    return context.order_item, context.bom_item, context.flow, context.nodes


def _node_context(session, production_item: ProductionItem, node_id: str):
    order_item, bom_item, flow, nodes = _item_context(session, production_item)
    node = nodes.get(node_id)
    if node is None:
        raise DomainError("flow_node_missing", "当前流程节点不存在")
    return order_item, bom_item, flow, nodes, node


def _production_item_unit_quantity(
    session, production_item: ProductionItem, bom_item: ProductBom | None
) -> int:
    if bom_item is not None:
        return bom_item.pcs
    _, _, _, nodes = _item_context(session, production_item)
    origin = nodes.get(production_item.origin_flow_node_id, {})
    return int(origin.get("output_pcs", 1))


def _normal_target(flow: dict, nodes: dict, node_id: str):
    return normal_target(flow, nodes, node_id)


def _target_department(session, node: dict) -> int:
    node_type = node.get("type")
    if node_type == "process":
        procedure = session.get(Procedure, node.get("procedure_id"))
        workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
        if workshop is None:
            raise DomainError("procedure_department_missing", "目标工艺没有有效部门")
        return workshop.department_id
    if node_type not in {"qc", "assembly"}:
        raise DomainError("flow_target_invalid", "目标节点类型不支持生产流转")
    code = "qc" if node_type == "qc" else "assembly"
    department_id = session.scalar(
        select(Department.id).where(Department.department_code == code)
    )
    if department_id is None:
        raise DomainError("department_not_found", "目标部门不存在")
    return department_id


def _move_to_node(
    session,
    production_item: ProductionItem,
    node: dict | None,
    quantity: int,
    source_node_id: str,
) -> int | None:
    if quantity <= 0 or node is None:
        return None
    # One stable item lock serializes every position change for that item.
    session.get(ProductionItem, production_item.id, with_for_update=True)
    department_id = _target_department(session, node)
    target = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item.id,
            Repository.flow_node_id == node["id"],
            Repository.source_flow_node_id == source_node_id,
            Repository.department_id == department_id,
        )
        .with_for_update()
    )
    if target is None:
        session.add(
            Repository(
                production_item_id=production_item.id,
                flow_node_id=node["id"],
                source_flow_node_id=source_node_id,
                department_id=department_id,
                quantity=quantity,
            )
        )
    else:
        target.quantity += quantity
    return department_id


def _consume_repository(session, repository: Repository, quantity: int) -> None:
    repository.quantity -= quantity
    if repository.quantity < 0:
        raise DomainError("repository_quantity_insufficient", "当前库存数量不足")
    if repository.quantity == 0:
        session.delete(repository)


def _mark_order_planned(session, production_item: ProductionItem) -> None:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = session.get(CustomerOrder, order_item.customer_order_id)
    session.refresh(customer_order, with_for_update=True)
    if customer_order.status == "confirmed":
        customer_order.status = "planned"
        customer_order.revision += 1
        customer_order.updated_at = datetime.now()


def _refresh_order_closed(session, production_item: ProductionItem) -> None:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = session.get(CustomerOrder, order_item.customer_order_id)
    session.refresh(customer_order, with_for_update=True)
    if customer_order.status != "planned":
        return
    position_count = session.scalar(
        select(func.count(Repository.id))
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == customer_order.id)
    )
    open_order_count = session.scalar(
        select(func.count(WorkOrder.id))
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(
            CustomerOrderItem.customer_order_id == customer_order.id,
            WorkOrder.status == "open",
        )
    )
    pending_qc_count = session.scalar(
        select(func.count(WorkOrderBatch.id))
        .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(
            CustomerOrderItem.customer_order_id == customer_order.id,
            WorkOrderBatch.recorded_at.is_(None),
        )
    )
    if not position_count and not open_order_count and not pending_qc_count:
        customer_order.status = "closed"
        customer_order.revision += 1
        customer_order.updated_at = datetime.now()


def create_work_order(
    repository_id: int,
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        repository = session.get(Repository, repository_id, with_for_update=True)
        if repository is None:
            raise DomainError("repository_not_found", "配件记录不存在", status_code=404)
        department = session.get(Department, repository.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)
        production_item = session.get(ProductionItem, repository.production_item_id)
        _, _, _, _, node = _node_context(session, production_item, repository.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有工艺节点可以开工单")
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None:
            raise DomainError("procedure_not_found", "工艺节点未关联有效工艺")
        worker = session.get(Worker, worker_id) if worker_id else None
        if worker_id and (
            worker is None
            or worker.department_id != repository.department_id
            or worker.workshop_id != procedure.workshop_id
        ):
            raise DomainError("worker_invalid", "工人不属于当前工艺所在车间")
        open_orders = session.scalars(
            select(WorkOrder).where(
                WorkOrder.repository_id == repository.id,
                WorkOrder.status == "open",
            )
        ).all()
        reserved = sum(
            item.quantity - item.completed_quantity for item in open_orders
        )
        if quantity > repository.quantity - reserved:
            raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")
        order = WorkOrder(
            repository_id=repository.id,
            production_item_id=production_item.id,
            procedure_id=procedure.id,
            procedure_name=procedure.procedure_name,
            flow_node_id=node["id"],
            worker_id=worker_id,
            quantity=quantity,
        )
        session.add(order)
        session.flush()
        _mark_order_planned(session, production_item)
        order.work_order_no = f"WO-{datetime.now():%Y%m%d}-{order.id:06d}"
        session.flush()
        return _serialize_work_order(session, order)


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
        input_items = [session.get(ProductionItem, item.production_item_id) for item in repositories]
        order_item_ids = {item.customer_order_item_id for item in input_items}
        node_ids = {item.flow_node_id for item in repositories}
        if len(order_item_ids) != 1 or len(node_ids) != 1:
            raise DomainError("assembly_inputs_mismatch", "装配输入必须属于同一订单明细和装配节点")
        _, _, _, _, assembly_node = _node_context(
            session, input_items[0], repositories[0].flow_node_id
        )
        if assembly_node.get("type") != "assembly":
            raise DomainError("assembly_node_invalid", "所选物料不在装配节点")
        incoming_edges = [
            edge
            for edge in _item_context(session, input_items[0])[2].get("edges", [])
            if edge.get("target_node_id") == assembly_node["id"]
            and edge.get("route_type", "normal") == "normal"
        ]
        expected_sources = [edge.get("source_node_id") for edge in incoming_edges]
        selected_sources = [repository.source_flow_node_id for repository in repositories]
        if not matches_assembly_sources(expected_sources, selected_sources):
            raise DomainError("assembly_inputs_incomplete", "必须选择装配节点的全部输入物料")
        worker = session.get(Worker, worker_id) if worker_id else None
        assembly_department = session.scalar(
            select(Department).where(Department.department_code == "assembly")
        )
        if worker_id and (worker is None or worker.department_id != assembly_department.id):
            raise DomainError("worker_invalid", "工人不属于装配部门")
        material_quantities: dict[int, int] = {}
        repositories_by_source: dict[str, list[tuple[Repository, ProductionItem]]] = {}
        for repository, input_item in zip(repositories, input_items, strict=True):
            repositories_by_source.setdefault(repository.source_flow_node_id, []).append(
                (repository, input_item)
            )
        for source_id, source_repositories in repositories_by_source.items():
            first_item = source_repositories[0][1]
            bom_item = (
                session.get(ProductBom, first_item.product_bom_id)
                if first_item.product_bom_id
                else None
            )
            remaining_required = required_material_quantity(
                quantity, _production_item_unit_quantity(session, first_item, bom_item)
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
                    material_quantities[repository.id] = allocated
                    remaining_required -= allocated
                if remaining_required == 0:
                    break
            if remaining_required:
                raise DomainError(
                    "assembly_quantity_exceeded",
                    f"来源节点 {source_id} 的可用物料不足",
                )
        order = WorkOrder(
            repository_id=None,
            production_item_id=input_items[0].id,
            procedure_id=None,
            procedure_name=assembly_node.get("label") or assembly_node.get("output_name") or "装配",
            flow_node_id=assembly_node["id"],
            worker_id=worker_id,
            quantity=quantity,
        )
        session.add(order)
        session.flush()
        _mark_order_planned(session, input_items[0])
        order.work_order_no = f"WO-{datetime.now():%Y%m%d}-{order.id:06d}"
        for repository in repositories:
            if repository.id not in material_quantities:
                continue
            session.add(
                WorkOrderMaterial(
                    work_order_id=order.id,
                    repository_id=repository.id,
                    production_item_id=repository.production_item_id,
                    quantity=material_quantities[repository.id],
                )
            )
        session.flush()
        return _serialize_work_order(session, order)


def submit_work_order(work_order_id: int, quantity: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        if order.procedure_id is None:
            return _submit_assembly_work_order(session, order, quantity, user_department)
        if order.repository_id is None:
            raise DomainError("work_order_closed", "工单来源库存已不存在")
        production_item = session.get(
            ProductionItem, order.production_item_id, with_for_update=True
        )
        repository = session.get(Repository, order.repository_id, with_for_update=True)
        if repository is None:
            raise DomainError("repository_not_found", "工单来源库存不存在")
        department = session.get(Department, repository.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)
        remaining = order.quantity - order.completed_quantity
        if quantity > remaining or quantity > repository.quantity:
            raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")
        _, _, flow, nodes, node = _node_context(
            session, production_item, repository.flow_node_id
        )
        target = _normal_target(flow, nodes, node["id"])
        batch = None
        if target is not None and target.get("type") == "qc":
            batch = WorkOrderBatch(
                work_order_id=order.id,
                submitted_quantity=quantity,
                flow_node_id=target["id"],
            )
            session.add(batch)
            session.flush()
            target_department_id = _move_to_node(
                session, production_item, target, quantity, node["id"]
            )
        else:
            if quantity != remaining:
                raise DomainError("partial_completion_not_allowed", "非 QC 工艺必须一次完成剩余数量")
            target_department_id = _move_to_node(
                session, production_item, target, quantity, node["id"]
            )
        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="process",
            source_flow_node_id=node["id"],
            target_flow_node_id=target.get("id") if target else None,
            source_department_id=repository.department_id,
            target_department_id=target_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id if batch else None,
        )
        will_delete_repository = repository.quantity == quantity
        if will_delete_repository:
            order.repository_id = None
        _consume_repository(session, repository, quantity)
        order.completed_quantity += quantity
        if quantity == remaining:
            order.status = "closed"
            order.closed_at = datetime.now()
        session.flush()
        _refresh_order_closed(session, production_item)
        return _serialize_work_order(session, order)


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_not_cancellable", "只有未完成工单可以取消")
        if order.completed_quantity:
            raise DomainError("work_order_started", "已经提交过产量的工单不能取消")
        procedure = session.get(Procedure, order.procedure_id) if order.procedure_id else None
        workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
        department = session.get(Department, workshop.department_id) if workshop else None
        department_code = department.department_code if department else "assembly"
        if user_department not in {"sys", department_code}:
            raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
        order.status = "cancelled"
        order.closed_at = datetime.now()
        session.flush()
        return _serialize_work_order(session, order)


def _submit_assembly_work_order(session, order: WorkOrder, quantity: int, user_department: str):
    if user_department not in {"sys", "assembly"}:
        raise DomainError("department_access_denied", "只有装配部门可以操作装配工单", status_code=403)
    remaining = order.quantity - order.completed_quantity
    if quantity != remaining:
        raise DomainError("partial_completion_not_allowed", "装配工单必须一次完成剩余数量")
    input_item = session.get(ProductionItem, order.production_item_id, with_for_update=True)
    order_item, _, flow, nodes, assembly_node = _node_context(
        session, input_item, order.flow_node_id
    )
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
        _consume_repository(session, repository, material.quantity)
    output_item = ProductionItem(
        customer_order_item_id=order_item.id,
        product_bom_id=None,
        origin_flow_node_id=assembly_node["id"],
    )
    session.add(output_item)
    session.flush()
    order.production_item_id = output_item.id
    target = _normal_target(flow, nodes, assembly_node["id"])
    output_quantity = quantity * int(assembly_node.get("output_pcs", 1))
    batch = None
    if target is not None and target.get("type") == "qc":
        batch = WorkOrderBatch(
            work_order_id=order.id,
            submitted_quantity=output_quantity,
            flow_node_id=target["id"],
        )
        session.add(batch)
        session.flush()
    target_department_id = _move_to_node(
        session,
        output_item,
        target,
        output_quantity,
        assembly_node["id"],
    )
    record_movement(
        session,
        production_item=output_item,
        quantity=output_quantity,
        movement_type="assembly_output",
        source_flow_node_id=assembly_node["id"],
        target_flow_node_id=target.get("id") if target else None,
        source_department_id=_target_department(session, assembly_node),
        target_department_id=target_department_id,
        work_order_id=order.id,
        work_order_batch_id=batch.id if batch else None,
    )
    order.completed_quantity += quantity
    order.status = "closed"
    order.closed_at = datetime.now()
    session.flush()
    _refresh_order_closed(session, output_item)
    return _serialize_work_order(session, order)


def inspect_batch(batch_id: int, payload, user_department: str) -> dict:
    if user_department not in {"sys", "qc"}:
        raise DomainError("qc_access_denied", "只有 QC 可以录入质检结果", status_code=403)
    with SessionLocal.begin() as session:
        qc_department = session.scalar(
            select(Department).where(Department.department_code == "qc")
        )
        qc_worker = session.get(Worker, payload.qc_worker_id)
        if qc_department is None or qc_worker is None or qc_worker.department_id != qc_department.id:
            raise DomainError("qc_worker_invalid", "请选择有效的 QC 工人")
        batch = session.get(WorkOrderBatch, batch_id, with_for_update=True)
        if batch is None:
            raise DomainError("qc_batch_not_found", "送检批次不存在", status_code=404)
        if batch.recorded_at is not None:
            raise DomainError("qc_batch_completed", "该批次已经完成质检")
        total = sum(
            (
                payload.qualified_quantity,
                payload.rework_quantity,
                payload.scrap_quantity,
                payload.lost_quantity,
            )
        )
        if total != batch.submitted_quantity:
            raise DomainError("qc_quantity_mismatch", "质检结果合计必须等于送检数量")
        if total - payload.qualified_quantity > 0 and not (payload.defect_reason or "").strip():
            raise DomainError("defect_reason_required", "存在异常数量时必须填写不良原因")
        order = session.get(WorkOrder, batch.work_order_id)
        production_item = session.get(
            ProductionItem, order.production_item_id, with_for_update=True
        )
        _, _, flow, nodes, qc_node = _node_context(
            session, production_item, batch.flow_node_id
        )
        qc_department_id = _target_department(session, qc_node)
        qc_repository = session.scalar(
            select(Repository)
            .where(
                Repository.production_item_id == production_item.id,
                Repository.flow_node_id == batch.flow_node_id,
                Repository.source_flow_node_id == order.flow_node_id,
                Repository.department_id == qc_department_id,
            )
            .with_for_update()
        )
        if qc_repository is None or qc_repository.quantity < total:
            raise DomainError("qc_repository_quantity_invalid", "QC 配件数量不足")
        approved = _normal_target(flow, nodes, qc_node["id"])
        rework_targets = [
            nodes.get(edge.get("target_node_id"))
            for edge in flow.get("edges", [])
            if edge.get("source_node_id") == qc_node["id"]
            and edge.get("route_type") == "rework"
        ]
        rework_targets = [item for item in rework_targets if item is not None]
        if payload.rework_quantity and len(rework_targets) != 1:
            raise DomainError("rework_target_missing", "QC 返工数量缺少唯一返工目标")
        approved_department_id = _move_to_node(
            session, production_item, approved, payload.qualified_quantity, qc_node["id"]
        )
        record_movement(
            session,
            production_item=production_item,
            quantity=payload.qualified_quantity,
            movement_type="qc_qualified",
            source_flow_node_id=qc_node["id"],
            target_flow_node_id=approved.get("id") if approved else None,
            source_department_id=qc_department_id,
            target_department_id=approved_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        if payload.rework_quantity:
            rework_department_id = _move_to_node(
                session,
                production_item,
                rework_targets[0],
                payload.rework_quantity,
                qc_node["id"],
            )
            record_movement(
                session,
                production_item=production_item,
                quantity=payload.rework_quantity,
                movement_type="qc_rework",
                source_flow_node_id=qc_node["id"],
                target_flow_node_id=rework_targets[0]["id"],
                source_department_id=qc_department_id,
                target_department_id=rework_department_id,
                work_order_id=order.id,
                work_order_batch_id=batch.id,
            )
        record_movement(
            session,
            production_item=production_item,
            quantity=payload.scrap_quantity,
            movement_type="scrap",
            source_flow_node_id=qc_node["id"],
            target_flow_node_id=None,
            source_department_id=qc_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        record_movement(
            session,
            production_item=production_item,
            quantity=payload.lost_quantity,
            movement_type="lost",
            source_flow_node_id=qc_node["id"],
            target_flow_node_id=None,
            source_department_id=qc_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        _consume_repository(session, qc_repository, total)
        batch.qualified_quantity = payload.qualified_quantity
        batch.rework_quantity = payload.rework_quantity
        batch.scrap_quantity = payload.scrap_quantity
        batch.lost_quantity = payload.lost_quantity
        batch.qc_worker_name = qc_worker.worker_name
        batch.defect_reason = (payload.defect_reason or "").strip() or None
        batch.recorded_at = datetime.now()
        session.flush()
        _refresh_order_closed(session, production_item)
        return _serialize_batch(batch)


def list_department_work_orders(
    department_code: str,
    page: int,
    page_size: int,
    production_item_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        statement = (
            select(WorkOrder)
            .outerjoin(Procedure, Procedure.id == WorkOrder.procedure_id)
            .outerjoin(Workshop, Workshop.id == Procedure.workshop_id)
            .order_by(WorkOrder.id.desc())
        )
        condition = (
            WorkOrder.procedure_id.is_(None)
            if department_code == "assembly"
            else Workshop.department_id == department.id
        )
        if production_item_id is not None:
            condition = condition & or_(
                WorkOrder.production_item_id == production_item_id,
                exists(
                    select(WorkOrderMaterial.id).where(
                        WorkOrderMaterial.work_order_id == WorkOrder.id,
                        WorkOrderMaterial.production_item_id == production_item_id,
                    )
                ),
            )
        filtered = statement.where(condition)
        total = session.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        ) or 0
        orders = session.scalars(
            filtered.offset((page - 1) * page_size).limit(page_size)
        ).all()
        order_ids = [order.id for order in orders]
        batch_cache: dict[int, list[WorkOrderBatch]] = {}
        material_cache: dict[int, list[int]] = {}
        if order_ids:
            for batch in session.scalars(
                select(WorkOrderBatch)
                .where(WorkOrderBatch.work_order_id.in_(order_ids))
                .order_by(WorkOrderBatch.id)
            ):
                batch_cache.setdefault(batch.work_order_id, []).append(batch)
            for work_order_id, production_item_id in session.execute(
                select(
                    WorkOrderMaterial.work_order_id,
                    WorkOrderMaterial.production_item_id,
                ).where(WorkOrderMaterial.work_order_id.in_(order_ids))
            ):
                material_cache.setdefault(work_order_id, []).append(production_item_id)
        session.info["work_order_batch_cache"] = batch_cache
        session.info["work_order_material_cache"] = material_cache
        return [_serialize_work_order(session, item) for item in orders], total


def list_department_workers(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        workers = session.scalars(
            select(Worker)
            .where(Worker.department_id == department.id)
            .order_by(Worker.worker_name, Worker.id)
        ).all()
        return [
            {
                "id": worker.id,
                "worker_name": worker.worker_name,
                "department_id": worker.department_id,
                "workshop_id": worker.workshop_id,
            }
            for worker in workers
        ]


def list_qc_batches(
    page: int, page_size: int, production_item_id: int | None = None
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        statement = select(WorkOrderBatch).join(
            WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id
        )
        if production_item_id is not None:
            statement = statement.where(
                or_(
                    WorkOrder.production_item_id == production_item_id,
                    exists(
                        select(WorkOrderMaterial.id).where(
                            WorkOrderMaterial.work_order_id == WorkOrder.id,
                            WorkOrderMaterial.production_item_id == production_item_id,
                        )
                    ),
                )
            )
        total = session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0
        batches = session.scalars(
            statement
            .order_by(WorkOrderBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        result = []
        for batch in batches:
            order = session.get(WorkOrder, batch.work_order_id)
            customer_order, bom_item, production_item = _work_order_context(session, order)
            part_no, part_name = _item_display(session, production_item)
            data = _serialize_batch(batch)
            data.update(
                {
                    "repository_id": _qc_repository_id(session, order, batch),
                    "production_item_id": order.production_item_id,
                    "work_order_no": order.work_order_no,
                    "customer_order_no": customer_order.customer_order_no,
                    "part_no": part_no,
                    "part_name": part_name,
                    "procedure_name": order.procedure_name,
                    "remaining_quantity": batch.submitted_quantity,
                }
            )
            result.append(data)
        return result, total
