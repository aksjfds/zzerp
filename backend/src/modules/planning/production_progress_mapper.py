"""Map loaded department progress context to the API response."""

from modules.planning.production_progress_cards import (
    build_progress_card,
    build_progress_work_order_row,
)


def build_department_progress_response(
    *,
    plan_item,
    plan,
    order,
    product,
    flow,
    nodes,
    department_route_nodes,
    procedures,
    workshops,
    departments,
    department_codes,
    production_item_ids,
    work_orders,
    serialized_work_orders,
    batches_by_order,
    workers,
    arrivals_by_node,
) -> dict:
    cards = []
    for sort_order, node in enumerate(department_route_nodes, start=1):
        workshop = workshops.get(node.get("workshop_id"))
        department = departments.get(workshop.department_id) if workshop else None
        node_type = node.get("type")
        if node_type == "assembly":
            department = department or department_codes.get("assembly")
        if node_type not in {"process", "assembly"} or department is None:
            continue
        node_orders = [
            item for item in work_orders
            if item.flow_node_id == node["id"] and item.status != "cancelled"
        ]
        procedure_ids = list(dict.fromkeys(
            item.procedure_id
            for item in node_orders
            if item.procedure_id is not None
        )) or [None]
        for procedure_id in procedure_ids:
            procedure = procedures.get(procedure_id) if procedure_id else None
            cards.append(build_progress_card(
                node=node,
                flow=flow,
                nodes=nodes,
                procedure=procedure,
                workshop=workshop,
                department=department,
                orders=[
                    item for item in node_orders
                    if item.procedure_id == procedure_id
                ],
                batches_by_order=batches_by_order,
                workers=workers,
                task_quantity=plan_item.planned_production_quantity,
                arrived_quantity=arrivals_by_node.get(node["id"], 0),
                sort_order=sort_order,
            ))

    for card in cards:
        for work_order_row in card["work_orders"]:
            work_order_row["work_order"] = serialized_work_orders[
                work_order_row["id"]
            ]

    work_order_rows = {
        item["id"]: item
        for card in cards
        for item in card["work_orders"]
    }
    node_by_id = {node["id"]: node for node in department_route_nodes}
    for work_order in work_orders:
        if work_order.id in work_order_rows:
            continue
        node = node_by_id.get(work_order.flow_node_id)
        if node is None:
            continue
        workshop = workshops.get(node.get("workshop_id"))
        procedure = (
            procedures.get(work_order.procedure_id)
            if work_order.procedure_id else None
        )
        row, _progress = build_progress_work_order_row(
            node=node,
            flow=flow,
            nodes=nodes,
            procedure=procedure,
            workshop=workshop,
            order=work_order,
            batches=batches_by_order.get(work_order.id, []),
            workers=workers,
        )
        row["work_order"] = serialized_work_orders[work_order.id]
        work_order_rows[work_order.id] = row

    return {
        "production_plan_item_id": plan_item.id,
        "production_item_ids": sorted(production_item_ids),
        "customer_order_no": order.customer_order_no,
        "factory_code": product.factory_code,
        "product_name": product.product_name,
        "part_no": plan_item.item_code,
        "part_name": plan_item.item_name,
        "plan_status": plan.status,
        "task_quantity": plan_item.planned_production_quantity,
        "cards": cards,
        "work_orders": [
            work_order_rows[work_order_id]
            for work_order_id in sorted(work_order_rows, reverse=True)
        ],
    }


__all__ = ["build_department_progress_response"]
