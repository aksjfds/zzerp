from __future__ import annotations

"""Customer-order production status calculations."""

from collections import defaultdict
from modules.production_core.model_api import Repository
from modules.sales.model_api import CustomerOrderItem
from modules.production_core.flow_api import assembly_material_key
from modules.production_core.operational_api import production_item_name, rework_pending_by_order
from modules.planning.order_production_context import OrderProductionReadContext

def _calculate_order_item_state(
    context: OrderProductionReadContext,
    order_item: CustomerOrderItem,
    flow: dict,
    nodes: dict[str, dict],
) -> dict:
    session = context.session
    bom_items = [
        item for item in context.bom_items.values()
        if item.product_id == order_item.product_id
        and item.product_version == order_item.product_version
    ]
    bom_by_id = {item.id: item for item in bom_items}
    production_items = context.production_items_by_order_item.get(order_item.id, [])
    production_item_ids = [item.id for item in production_items]
    repositories = [
        repository
        for item_id in production_item_ids
        for repository in context.repositories_by_item.get(item_id, [])
    ]
    movements = [
        movement
        for item_id in production_item_ids
        for movement in context.movements_by_item.get(item_id, [])
    ]
    work_orders = [
        work_order
        for item_id in production_item_ids
        for work_order in context.work_orders_by_item.get(item_id, [])
    ]
    work_order_batches = [
        batch
        for work_order in work_orders
        for batch in context.batches_by_order.get(work_order.id, [])
    ]
    batches_by_id = {batch.id: batch for batch in work_order_batches}
    pending_qc_by_node: dict[str, int] = defaultdict(int)
    for movement in movements:
        batch = batches_by_id.get(movement.work_order_batch_id)
        if (
            batch is not None
            and batch.recorded_at is None
            and movement.target_flow_node_id
            and movement.movement_type in {
                "process",
                "purchase_receipt",
                "assembly_output",
            }
        ):
            pending_qc_by_node[movement.target_flow_node_id] += (
                batch.submitted_quantity
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
        production_item = context.display.production_items.get(
            repository.production_item_id
        )
        source_name = (
            production_item_name(
                session,
                production_item,
                set(),
                context.display,
            )
            if production_item
            else "未知来源"
        )
        current_inputs[repository.flow_node_id][source_name] += repository.quantity
    for flow_node_id, quantity in pending_qc_by_node.items():
        if flow_node_id:
            current_by_node[flow_node_id] += int(quantity or 0)
    held_qc_by_node: dict[str, int] = defaultdict(int)
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
        production_item = context.display.production_items.get(
            movement.production_item_id
        )
        source_name = (
            production_item_name(
                session,
                production_item,
                set(),
                context.display,
            )
            if production_item else "未知来源"
        )
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
                first_item = context.display.production_items.get(
                    source_repositories[0].production_item_id
                )
                bom_item = (
                    context.bom_items.get(first_item.product_bom_id)
                    if first_item and first_item.product_bom_id else None
                )
                unit_quantity = bom_item.pcs if bom_item else int(
                    nodes.get(
                        first_item.origin_flow_node_id if first_item else "",
                        {},
                    ).get("output_pcs", 1)
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
    return {"node_stats": stats, "edge_stats": edge_stats}

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
