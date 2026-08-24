"""Calculate material arrival quantities from a loaded progress context."""

from collections import defaultdict

from modules.planning.assembly_progress import assembly_arrived_output_quantity


ARRIVAL_MOVEMENT_TYPES = {
    "initial",
    "inventory_issue",
    "process",
    "purchase_receipt",
    "assembly_output",
}
QC_FORWARD_MOVEMENT_TYPES = {"qc_qualified"}


def calculate_progress_arrivals(
    *,
    plan_item,
    flow,
    nodes,
    route_node_ids,
    order_production_items,
    movements,
    work_order_by_id,
    bom_items,
) -> dict[str, int]:
    arrivals_by_node: dict[str, int] = defaultdict(int)
    if plan_item.item_type == "assembly":
        assembly_node = nodes.get(plan_item.flow_node_id, {})
        arrivals_by_node[plan_item.flow_node_id] = (
            assembly_arrived_output_quantity(
                flow,
                nodes,
                plan_item.flow_node_id,
                int(assembly_node.get("output_pcs") or 1),
                order_production_items,
                movements,
                bom_items,
            )
        )
        for node_id in route_node_ids - {plan_item.flow_node_id}:
            arrivals_by_node[node_id] = sum(
                movement.quantity
                for movement in movements
                if movement.target_flow_node_id == node_id
                and movement.source_flow_node_id != node_id
            )
        return dict(arrivals_by_node)

    for movement in movements:
        movement_order = work_order_by_id.get(movement.work_order_id)
        is_qc_forward = (
            movement.movement_type in QC_FORWARD_MOVEMENT_TYPES
            and movement_order is not None
            and movement.target_flow_node_id != movement_order.flow_node_id
        )
        if (
            (
                movement.movement_type in ARRIVAL_MOVEMENT_TYPES
                or is_qc_forward
            )
            and movement.target_flow_node_id in route_node_ids
            and movement.source_flow_node_id != movement.target_flow_node_id
        ):
            arrivals_by_node[movement.target_flow_node_id] += movement.quantity
    return dict(arrivals_by_node)


__all__ = ["calculate_progress_arrivals"]
