from collections import defaultdict

from sqlalchemy import func, select

from database import SessionLocal
from services.production_flow import load_product_flow
from models.engineering import Product, ProductBom
from models.production import (
    ProcedureTagStock,
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError
from services.work_order_presenters import production_item_name


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
        flow, nodes = {"schema_version": 2, "nodes": [], "edges": []}, {}
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
    tag_stocks = (
        session.scalars(
            select(ProcedureTagStock).where(
                ProcedureTagStock.production_item_id.in_(production_item_ids)
            )
        ).all()
        if production_item_ids
        else []
    )
    movements = (
        session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(production_item_ids)
            )
        ).all()
        if production_item_ids
        else []
    )
    pending_qc_by_node = (
        session.execute(
            select(
                WorkOrder.flow_node_id,
                func.sum(WorkOrderBatch.submitted_quantity),
            )
            .join(WorkOrderBatch, WorkOrderBatch.work_order_id == WorkOrder.id)
            .where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrderBatch.recorded_at.is_(None),
            )
            .group_by(WorkOrder.flow_node_id)
        ).all()
        if production_item_ids
        else []
    )

    current_by_node: dict[str, int] = defaultdict(int)
    current_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for repository in repositories:
        current_by_node[repository.flow_node_id] += repository.quantity
        production_item = session.get(ProductionItem, repository.production_item_id)
        source_name = (
            production_item_name(session, production_item, set())
            if production_item
            else "未知来源"
        )
        current_inputs[repository.flow_node_id][source_name] += repository.quantity
    for stock in tag_stocks:
        current_by_node[stock.flow_node_id] += stock.quantity
        production_item = session.get(ProductionItem, stock.production_item_id)
        source_name = (
            production_item_name(session, production_item, set())
            if production_item
            else "未知来源"
        )
        current_inputs[stock.flow_node_id][source_name] += stock.quantity
    for flow_node_id, quantity in pending_qc_by_node:
        current_by_node[flow_node_id] += int(quantity or 0)

    material_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    entered_by_node: dict[str, int] = defaultdict(int)
    transferred_by_node: dict[str, int] = defaultdict(int)
    abnormal_by_node: dict[str, int] = defaultdict(int)
    assembly_output_by_node: dict[str, int] = defaultdict(int)
    for movement in movements:
        if (
            movement.target_flow_node_id
            and movement.target_flow_node_id != movement.source_flow_node_id
        ):
            entered_by_node[movement.target_flow_node_id] += movement.quantity
        leaves_source_node = (
            movement.target_flow_node_id != movement.source_flow_node_id
            and (
                movement.target_flow_node_id is not None
                or movement.work_order_batch_id is None
                or movement.movement_type == "qc_qualified"
            )
        )
        if (
            movement.source_flow_node_id
            and movement.movement_type not in {"scrap", "lost"}
            and leaves_source_node
        ):
            transferred_by_node[movement.source_flow_node_id] += movement.quantity
        if movement.source_flow_node_id and movement.movement_type in {"scrap", "lost"}:
            abnormal_by_node[movement.source_flow_node_id] += movement.quantity
        if movement.movement_type == "assembly_output" and movement.source_flow_node_id:
            assembly_output_by_node[movement.source_flow_node_id] += movement.quantity
        if movement.movement_type != "assembly_input" or not movement.source_flow_node_id:
            continue
        production_item = session.get(ProductionItem, movement.production_item_id)
        source_name = production_item_name(session, production_item, set()) if production_item else "未知来源"
        material_inputs[movement.source_flow_node_id][source_name] += movement.quantity

    stats = []
    for node in flow.get("nodes", []):
        node_id = node["id"]
        node_type = node.get("type")
        current = current_by_node[node_id]
        entered = entered_by_node[node_id]
        transferred = transferred_by_node[node_id]
        abnormal = abnormal_by_node[node_id]
        input_details: dict[str, int] = {}
        output_quantity = 0
        if node_type == "part":
            bom_item = bom_by_id.get(node.get("bom_item_id"))
            entered = order_item.quantity * bom_item.pcs if bom_item else 0
            transferred = transferred_by_node[node_id]
            current = max(entered - transferred, 0)
        elif node_type == "assembly":
            input_details = dict(current_inputs[node_id])
            for name, quantity in material_inputs[node_id].items():
                input_details[name] = input_details.get(name, 0) + quantity
            output_quantity = assembly_output_by_node[node_id]
            output_pcs = int(node.get("output_pcs", 1))
            transferred = output_quantity // output_pcs if output_pcs else 0
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
