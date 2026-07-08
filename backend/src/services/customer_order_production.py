from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from services.production_flow import load_product_flow
from models.engineering import Product, ProductBom
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch, WorkOrderMaterial
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError


def get_customer_order_production(order_id: int) -> dict:
    with SessionLocal() as session:
        order = session.get(CustomerOrder, order_id)
        if order is None:
            raise DomainError("customer_order_not_found", "客户订单不存在", status_code=404)
        products = [
            _serialize_order_item(session, item)
            for item in session.scalars(
                select(CustomerOrderItem).where(CustomerOrderItem.customer_order_id == order.id)
            )
        ]
        return {"customer_order_id": order.id, "status": order.status, "products": products}


def _serialize_order_item(session, order_item: CustomerOrderItem) -> dict:
    product = session.get(Product, order_item.product_id)
    try:
        flow, nodes = load_product_flow(
            session, order_item.product_id, order_item.product_version
        )
    except DomainError:
        flow, nodes = {"schema_version": 1, "nodes": [], "edges": []}, {}
    bom_items = session.scalars(
        select(ProductBom).where(
            ProductBom.product_id == order_item.product_id,
            ProductBom.product_version == order_item.product_version,
        )
    ).all()
    bom_by_id = {item.id: item for item in bom_items}
    production_items = session.scalars(
        select(ProductionItem).where(ProductionItem.customer_order_item_id == order_item.id)
    ).all()
    production_item_ids = [item.id for item in production_items]
    repositories = (
        session.scalars(
            select(Repository).where(Repository.production_item_id.in_(production_item_ids))
        ).all()
        if production_item_ids
        else []
    )
    work_orders = (
        session.scalars(
            select(WorkOrder).where(WorkOrder.production_item_id.in_(production_item_ids))
        ).all()
        if production_item_ids
        else []
    )
    work_order_ids = [item.id for item in work_orders]
    batches = (
        session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.work_order_id.in_(work_order_ids))
        ).all()
        if work_order_ids
        else []
    )
    materials = (
        session.scalars(
            select(WorkOrderMaterial).where(WorkOrderMaterial.work_order_id.in_(work_order_ids))
        ).all()
        if work_order_ids
        else []
    )

    current_by_node: dict[str, int] = defaultdict(int)
    current_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for repository in repositories:
        current_by_node[repository.flow_node_id] += repository.quantity
        source = nodes.get(repository.source_flow_node_id, {})
        source_name = source.get("output_name") or source.get("label", "未知来源")
        current_inputs[repository.flow_node_id][source_name] += repository.quantity

    orders_by_node: dict[str, list[WorkOrder]] = defaultdict(list)
    orders_by_id = {item.id: item for item in work_orders}
    for work_order in work_orders:
        orders_by_node[work_order.flow_node_id].append(work_order)
    batches_by_node: dict[str, list[WorkOrderBatch]] = defaultdict(list)
    for batch in batches:
        batches_by_node[batch.flow_node_id].append(batch)
    material_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for material in materials:
        work_order = orders_by_id.get(material.work_order_id)
        if work_order is None:
            continue
        production_item = session.get(ProductionItem, material.production_item_id)
        source_node = nodes.get(production_item.origin_flow_node_id, {}) if production_item else {}
        source_name = source_node.get("output_name") or source_node.get("label", "未知来源")
        material_inputs[work_order.flow_node_id][source_name] += material.quantity

    produced_bom_ids = {item.product_bom_id for item in production_items if item.product_bom_id}
    stats = []
    for node in flow.get("nodes", []):
        node_id = node["id"]
        node_type = node.get("type")
        current = current_by_node[node_id]
        node_orders = orders_by_node[node_id]
        node_batches = batches_by_node[node_id]
        entered = current + sum(item.completed_quantity for item in node_orders)
        transferred = sum(item.completed_quantity for item in node_orders)
        abnormal = 0
        input_details: dict[str, int] = {}
        output_quantity = 0
        if node_type == "part":
            bom_item = bom_by_id.get(node.get("bom_item_id"))
            entered = order_item.quantity * bom_item.pcs if bom_item else 0
            transferred = entered if bom_item and bom_item.id in produced_bom_ids else 0
            current = max(entered - transferred, 0)
        elif node_type == "qc":
            entered = sum(item.submitted_quantity for item in node_batches)
            transferred = sum(
                (item.qualified_quantity or 0) + (item.rework_quantity or 0)
                for item in node_batches
            )
            abnormal = sum(
                (item.scrap_quantity or 0) + (item.lost_quantity or 0)
                for item in node_batches
            )
            current = max(entered - transferred - abnormal, 0)
        elif node_type == "assembly":
            input_details = dict(current_inputs[node_id])
            for name, quantity in material_inputs[node_id].items():
                input_details[name] = input_details.get(name, 0) + quantity
            transferred = sum(item.completed_quantity for item in node_orders)
            output_quantity = transferred * int(node.get("output_pcs", 1))
            entered = 0
            current = 0
        stats.append(
            {
                "flow_node_id": node_id,
                "node_type": node_type,
                "current_quantity": current,
                "entered_quantity": entered,
                "transferred_quantity": transferred,
                "abnormal_quantity": abnormal,
                "output_quantity": output_quantity,
                "input_details": input_details,
            }
        )
    return {
        "customer_order_item_id": order_item.id,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_version": order_item.product_version,
        "order_quantity": order_item.quantity,
        "process_flow": flow,
        "node_stats": stats,
    }
