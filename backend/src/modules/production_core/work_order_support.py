from sqlalchemy import func, select

from modules.engineering.model_api import ProductBom
from domain.time import utc_now
from modules.organization.model_api import Department, Procedure, Workshop
from modules.assembly.model_api import WorkOrderMaterial
from modules.quality.model_api import WorkOrderBatch
from modules.standard_execution.model_api import ProcedureTagStock
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.flow import (
    ProductionFlowContext,
    load_product_flow,
    load_production_flow,
)


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
    if node_type == "shipping":
        department_code = "warehouse"
    elif node_type == "assembly":
        department_code = "assembly"
    else:
        raise DomainError("flow_target_invalid", "目标节点类型不支持生产流转")
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
    if node.get("type") == "shipping":
        return department_id
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
    remaining_quantity = repository.quantity - quantity
    if remaining_quantity < 0:
        raise DomainError("repository_quantity_insufficient", "当前库存数量不足")
    if remaining_quantity == 0:
        # Older closed work orders/material allocations can still point at the
        # same position after earlier partial consumption. Release every such
        # reference before removing the exhausted row; immutable movements keep
        # the historical source position.
        referencing_orders = session.scalars(
            select(WorkOrder)
            .where(WorkOrder.repository_id == repository.id)
            .with_for_update()
        ).all()
        referencing_materials = session.scalars(
            select(WorkOrderMaterial)
            .where(WorkOrderMaterial.repository_id == repository.id)
            .with_for_update()
        ).all()
        for order in referencing_orders:
            order.repository_id = None
        for material in referencing_materials:
            material.repository_id = None
        # Do not write quantity=0 because the repository check requires a
        # positive value.
        session.flush()
        session.delete(repository)
    else:
        repository.quantity = remaining_quantity


def mark_order_planned(session, production_item: ProductionItem) -> None:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = session.get(CustomerOrder, order_item.customer_order_id)
    session.refresh(customer_order, with_for_update=True)
    if customer_order.status == "confirmed":
        customer_order.status = "planned"
        customer_order.revision += 1
        customer_order.updated_at = utc_now()


def refresh_order_closed(session, production_item: ProductionItem) -> None:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    customer_order = session.get(CustomerOrder, order_item.customer_order_id)
    session.refresh(customer_order, with_for_update=True)
    if customer_order.status != "planned":
        return

    repository_count = session.scalar(
        select(func.count(Repository.id))
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == customer_order.id)
    )
    tag_stock_count = session.scalar(
        select(func.count(ProcedureTagStock.id))
        .join(
            ProductionItem,
            ProductionItem.id == ProcedureTagStock.production_item_id,
        )
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionItem.customer_order_item_id,
        )
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
    held_qc_qualified = session.scalar(
        select(func.coalesce(func.sum(ProductionMovement.quantity), 0))
        .join(ProductionItem, ProductionItem.id == ProductionMovement.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(
            CustomerOrderItem.customer_order_id == customer_order.id,
            ProductionMovement.movement_type == "qc_qualified",
            ProductionMovement.source_flow_node_id == ProductionMovement.target_flow_node_id,
            ProductionMovement.source_department_id
            == ProductionMovement.target_department_id,
        )
    ) or 0
    dispatched_qc = session.scalar(
        select(func.coalesce(func.sum(ProductionMovement.quantity), 0))
        .join(ProductionItem, ProductionItem.id == ProductionMovement.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(
            CustomerOrderItem.customer_order_id == customer_order.id,
            ProductionMovement.movement_type == "qc_dispatch",
        )
    ) or 0
    shipping_complete = all(
        _order_item_shipping_complete(session, item)
        for item in session.scalars(
            select(CustomerOrderItem).where(
                CustomerOrderItem.customer_order_id == customer_order.id
            )
        )
    )
    if (
        not repository_count
        and not tag_stock_count
        and not open_order_count
        and not pending_qc_count
        and int(held_qc_qualified) <= int(dispatched_qc)
        and shipping_complete
    ):
        customer_order.status = "closed"
        customer_order.revision += 1
        customer_order.updated_at = utc_now()


def _order_item_shipping_complete(session, order_item: CustomerOrderItem) -> bool:
    flow, nodes = load_product_flow(
        session,
        order_item.product_id,
        order_item.product_version,
    )
    shipping_nodes = [node for node in nodes.values() if node.get("type") == "shipping"]
    if len(shipping_nodes) != 1:
        return False
    shipping_node = shipping_nodes[0]
    unit_quantity = terminal_unit_quantity(session, flow, nodes, shipping_node["id"])
    if unit_quantity is None:
        return False
    shipped = session.scalar(
        select(func.coalesce(func.sum(ProductionMovement.quantity), 0))
        .join(ProductionItem, ProductionItem.id == ProductionMovement.production_item_id)
        .where(
            ProductionItem.customer_order_item_id == order_item.id,
            ProductionMovement.movement_type == "qc_dispatch",
            ProductionMovement.target_flow_node_id == shipping_node["id"],
        )
    ) or 0
    return int(shipped) >= order_item.quantity * unit_quantity


def terminal_unit_quantity(session, flow: dict, nodes: dict[str, dict], node_id: str) -> int | None:
    incoming = {
        edge.get("source_node_id")
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
    }
    incoming.discard(None)
    if len(incoming) != 1:
        return None
    source_id = next(iter(incoming))
    source = nodes.get(source_id)
    if source is None:
        return None
    source_type = source.get("type")
    if source_type == "assembly":
        return int(source.get("output_pcs", 1))
    if source_type == "part":
        bom = session.get(ProductBom, source.get("bom_item_id"))
        return bom.pcs if bom is not None else None
    if source_type in {"process", "qc"}:
        return terminal_unit_quantity(session, flow, nodes, source_id)
    return None
