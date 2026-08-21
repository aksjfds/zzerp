from collections import defaultdict

from sqlalchemy import func, select

from database import SessionLocal
from modules.engineering.model_api import Product, ProductBom
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.quality.model_api import WorkOrderBatch
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.operational_api import load_product_flow
from modules.production_core.operational_api import production_item_name
from modules.production_core.operational_api import rework_pending_by_order
from modules.production_core.operational_api import production_item_unit_quantity
from modules.production_core.flow import assembly_material_key


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
        flow, nodes = {"schema_version": 4, "nodes": [], "edges": []}, {}
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
    movements = (
        session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(production_item_ids)
            )
        ).all()
        if production_item_ids
        else []
    )
    work_orders = (
        list(session.scalars(
            select(WorkOrder).where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrder.work_order_type.in_(("standard", "assembly")),
            )
        ).all())
        if production_item_ids
        else []
    )
    work_order_ids = [item.id for item in work_orders]
    work_order_batches = (
        list(session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_(work_order_ids)
            )
        ).all())
        if work_order_ids
        else []
    )
    pending_qc_by_node = (
        session.execute(
            select(
                ProductionMovement.target_flow_node_id,
                func.sum(WorkOrderBatch.submitted_quantity),
            )
            .join(
                ProductionMovement,
                ProductionMovement.work_order_batch_id == WorkOrderBatch.id,
            )
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrderBatch.recorded_at.is_(None),
                ProductionMovement.movement_type.in_(
                    ("process", "purchase_receipt", "assembly_output")
                ),
            )
            .group_by(ProductionMovement.target_flow_node_id)
        ).all()
        if production_item_ids
        else []
    )

    current_by_node: dict[str, int] = defaultdict(int)
    current_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    current_repository_sources: dict[str, dict[str, list[Repository]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for repository in repositories:
        current_by_node[repository.flow_node_id] += repository.quantity
        current_repository_sources[repository.flow_node_id][
            repository.source_flow_node_id
        ].append(repository)
        production_item = session.get(ProductionItem, repository.production_item_id)
        source_name = (
            production_item_name(session, production_item, set())
            if production_item
            else "未知来源"
        )
        current_inputs[repository.flow_node_id][source_name] += repository.quantity
    for flow_node_id, quantity in pending_qc_by_node:
        if flow_node_id:
            current_by_node[flow_node_id] += int(quantity or 0)
    held_qc_by_node: dict[str, int] = defaultdict(int)
    batch_ids = {
        movement.work_order_batch_id
        for movement in movements
        if movement.work_order_batch_id is not None
    }
    batches_by_id = {
        batch.id: batch
        for batch in session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.id.in_(batch_ids))
        )
    } if batch_ids else {}
    for movement in movements:
        if (
            movement.movement_type == "qc_qualified"
            and movement.source_flow_node_id == movement.target_flow_node_id
            and movement.source_department_id == movement.target_department_id
            and movement.target_flow_node_id
        ):
            held_qc_by_node[movement.target_flow_node_id] += movement.quantity
    for flow_node_id, quantity in held_qc_by_node.items():
        current_by_node[flow_node_id] += max(quantity, 0)
    pending_rework = rework_pending_by_order(work_order_batches)
    pending_rework_by_node: dict[str, int] = defaultdict(int)
    for work_order in work_orders:
        quantity = pending_rework.get(work_order.id, 0)
        current_by_node[work_order.flow_node_id] += quantity
        pending_rework_by_node[work_order.flow_node_id] += quantity

    material_inputs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    entered_by_node: dict[str, int] = defaultdict(int)
    transferred_by_node: dict[str, int] = defaultdict(int)
    transferred_by_edge: dict[str, int] = defaultdict(int)
    abnormal_by_node: dict[str, int] = defaultdict(int)
    assembly_output_by_node: dict[str, int] = defaultdict(int)
    internal_process_returns: dict[str, int] = defaultdict(int)
    process_abnormal_by_node: dict[str, int] = defaultdict(int)
    work_order_by_id = {order.id: order for order in work_orders}
    edge_id_by_nodes = {
        (edge["source_node_id"], edge["target_node_id"]): edge["id"]
        for edge in flow.get("edges", [])
    }
    for movement in movements:
        movement_order = work_order_by_id.get(movement.work_order_id)
        if (
            movement.target_flow_node_id
            and movement.movement_type in {"qc_qualified", "qc_rework"}
            and movement_order is not None
            and movement_order.flow_node_id == movement.target_flow_node_id
        ):
            internal_process_returns[
                movement.target_flow_node_id
            ] += movement.quantity
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
            if movement_order is not None:
                process_abnormal_by_node[
                    movement_order.flow_node_id
                ] += movement.quantity
        edge_id = edge_id_by_nodes.get(
            (movement.source_flow_node_id, movement.target_flow_node_id)
        )
        if edge_id is not None:
            transferred_by_edge[edge_id] += movement.quantity
        movement_batch = batches_by_id.get(movement.work_order_batch_id)
        if (
            movement.movement_type == "assembly_output"
            and movement.source_flow_node_id
            and (
                movement_batch is None
                or movement_batch.rework_source_batch_id is None
            )
        ):
            assembly_output_by_node[movement.source_flow_node_id] += movement.quantity
        if movement.movement_type != "assembly_input" or not movement.source_flow_node_id:
            continue
        production_item = session.get(ProductionItem, movement.production_item_id)
        source_name = production_item_name(session, production_item, set()) if production_item else "未知来源"
        material_inputs[movement.source_flow_node_id][source_name] += movement.quantity

    process_totals_by_node = {
        node["id"]: _process_node_totals(
            entered_by_node[node["id"]],
            internal_process_returns[node["id"]],
            current_by_node[node["id"]],
            process_abnormal_by_node[node["id"]],
        )
        for node in flow.get("nodes", [])
        if node.get("type") == "process"
    }
    node_type_by_id = {
        node["id"]: node.get("type")
        for node in flow.get("nodes", [])
    }
    qc_totals_by_node = {
        node["id"]: _qc_node_totals(
            [
                (
                    process_totals_by_node[source_id][1]
                    if node_type_by_id.get(source_id) == "process"
                    else transferred_by_edge[edge["id"]]
                )
                for edge in flow.get("edges", [])
                if edge["target_node_id"] == node["id"]
                for source_id in [edge["source_node_id"]]
            ],
            current_by_node[node["id"]],
            abnormal_by_node[node["id"]],
        )
        for node in flow.get("nodes", [])
        if node.get("type") == "qc"
    }

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
            transferred = transferred_by_node[node_id]
            entered = transferred
            current = max(entered - transferred, 0)
        elif node_type == "process":
            abnormal = process_abnormal_by_node[node_id]
            entered, transferred = process_totals_by_node[node_id]
        elif node_type == "qc":
            entered, transferred = qc_totals_by_node[node_id]
        elif node_type == "assembly":
            input_details = dict(current_inputs[node_id])
            for name, quantity in material_inputs[node_id].items():
                input_details[name] = input_details.get(name, 0) + quantity
            output_quantity = assembly_output_by_node[node_id]
            output_pcs = int(node.get("output_pcs", 1))
            transferred = output_quantity // output_pcs if output_pcs else 0
            required_source_ids = {
                edge["source_node_id"]
                for edge in flow.get("edges", [])
                if edge["target_node_id"] == node_id
            }
            required_source_groups: dict[str, list[str]] = defaultdict(list)
            for source_id in required_source_ids:
                material_key = assembly_material_key(flow, nodes, source_id)
                if material_key is not None:
                    required_source_groups[material_key].append(source_id)
            source_capacities = []
            for source_ids in required_source_groups.values():
                source_repositories = [
                    repository
                    for source_id in source_ids
                    for repository in current_repository_sources[node_id].get(source_id, [])
                ]
                if not source_repositories:
                    source_capacities.append(0)
                    continue
                first_item = session.get(
                    ProductionItem,
                    source_repositories[0].production_item_id,
                )
                bom_item = (
                    session.get(ProductBom, first_item.product_bom_id)
                    if first_item and first_item.product_bom_id else None
                )
                unit_quantity = (
                    production_item_unit_quantity(session, first_item, bom_item)
                    if first_item else 1
                )
                source_quantity = sum(
                    repository.quantity for repository in source_repositories
                )
                source_capacities.append(
                    source_quantity // unit_quantity if unit_quantity else 0
                )
            current = (
                min(source_capacities, default=0)
                + pending_rework_by_node[node_id]
            )
        elif node_type == "shipping":
            output_quantity = entered
            transferred = entered
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
    transferred_by_node_id = {
        item["flow_node_id"]: item["transferred_quantity"]
        for item in stats
    }
    edge_stats = [
        {
            "flow_edge_id": edge["id"],
            "transferred_quantity": transferred_by_node_id.get(
                edge["source_node_id"],
                transferred_by_edge[edge["id"]],
            ),
        }
        for edge in flow.get("edges", [])
    ]
    return {
        "customer_order_item_id": order_item.id,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_version": order_item.product_version,
        "order_quantity": order_item.quantity,
        "process_flow": flow,
        "node_stats": stats,
        "edge_stats": edge_stats,
    }


def _process_node_totals(
    recorded_entered: int,
    internal_returned: int,
    current: int,
    abnormal: int,
) -> tuple[int, int]:
    entered = max(recorded_entered - internal_returned, 0)
    transferred = max(entered - current - abnormal, 0)
    return entered, transferred


def _qc_node_totals(
    incoming_quantities: list[int],
    current: int,
    abnormal: int,
) -> tuple[int, int]:
    entered = sum(incoming_quantities)
    transferred = max(entered - current - abnormal, 0)
    return entered, transferred
