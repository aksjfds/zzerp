from datetime import datetime

from sqlalchemy import func, select

from models.engineering import ProductBom
from models.organization import Department, Procedure, Workshop
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError
from services.production_flow import ProductionFlowContext, load_production_flow


def flow_context(session, production_item: ProductionItem) -> ProductionFlowContext:
    return load_production_flow(session, production_item)


def node_context(
    session,
    production_item: ProductionItem,
    node_id: str,
) -> tuple[ProductionFlowContext, dict]:
    context = flow_context(session, production_item)
    return context, context.node(node_id)


def production_item_unit_quantity(
    session,
    production_item: ProductionItem,
    bom_item: ProductBom | None,
) -> int:
    if bom_item is not None:
        return bom_item.pcs
    context = flow_context(session, production_item)
    origin = context.nodes.get(production_item.origin_flow_node_id, {})
    return int(origin.get("output_pcs", 1))


def target_department_id(session, node: dict) -> int:
    node_type = node.get("type")
    if node_type == "process":
        procedure = session.get(Procedure, node.get("procedure_id"))
        workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
        if workshop is None:
            raise DomainError("procedure_department_missing", "目标工艺没有有效部门")
        return workshop.department_id
    if node_type not in {"qc", "assembly"}:
        raise DomainError("flow_target_invalid", "目标节点类型不支持生产流转")
    department_code = "qc" if node_type == "qc" else "assembly"
    department_id = session.scalar(
        select(Department.id).where(Department.department_code == department_code)
    )
    if department_id is None:
        raise DomainError("department_not_found", "目标部门不存在")
    return department_id


def move_to_node(
    session,
    production_item: ProductionItem,
    node: dict | None,
    quantity: int,
    source_node_id: str,
) -> int | None:
    if quantity <= 0 or node is None:
        return None
    session.get(ProductionItem, production_item.id, with_for_update=True)
    department_id = target_department_id(session, node)
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


def consume_repository(session, repository: Repository, quantity: int) -> None:
    repository.quantity -= quantity
    if repository.quantity < 0:
        raise DomainError("repository_quantity_insufficient", "当前库存数量不足")
    if repository.quantity == 0:
        session.delete(repository)


def mark_order_planned(session, production_item: ProductionItem) -> None:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = session.get(CustomerOrder, order_item.customer_order_id)
    session.refresh(customer_order, with_for_update=True)
    if customer_order.status == "confirmed":
        customer_order.status = "planned"
        customer_order.revision += 1
        customer_order.updated_at = datetime.now()


def refresh_order_closed(session, production_item: ProductionItem) -> None:
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
