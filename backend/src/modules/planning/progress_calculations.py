from __future__ import annotations

"""Pure and context-bound production-progress calculations."""

from collections import defaultdict
from modules.production_core.model_api import WorkOrder, WorkOrderBatch
from modules.production_core.operational_api import calculate_work_order_progress
from modules.planning.progress_routes import progress_route_nodes

def _process_completion_summary(
    work_orders: list[WorkOrder],
    batches_by_order: dict[int, list[WorkOrderBatch]],
) -> int:
    completed_quantity = 0
    for work_order in work_orders:
        batches = batches_by_order.get(work_order.id, [])
        progress = calculate_work_order_progress(work_order, batches)
        completed_quantity += progress.qualified_quantity
    return completed_quantity

def _physical_route(context, origin_node_id: str) -> list[dict]:
    return progress_route_nodes(
        context.flow,
        context.nodes,
        origin_node_id,
    )



def _node_department(node, department_by_code, workshops):
    node_type = node.get("type")
    if node_type in {"process", "assembly"}:
        workshop = workshops.get(node.get("workshop_id"))
        return (
            next(
                (
                    department
                    for department in department_by_code.values()
                    if workshop and department.id == workshop.department_id
                ),
                None,
            )
        )
    code = {
        "qc": "qc",
        "finished_inbound": "finished",
    }.get(node_type)
    return department_by_code.get(code) if code else None

def _node_workshop(node, workshops):
    if node.get("type") not in {"process", "assembly"}:
        return None
    return workshops.get(node.get("workshop_id"))

def _assembly_target_quantity(context, production_item, work_orders) -> int:
    output_pcs = int(
        context.nodes.get(production_item.origin_flow_node_id, {}).get(
            "output_pcs",
            1,
        )
    )
    return sum(
        order.quantity * output_pcs
        for order in work_orders
        if (
            order.work_order_type == "assembly"
            and order.status != "cancelled"
        )
    )

def _empty_cell() -> dict:
    return {
        "in_route": False,
        "waiting_quantity": 0,
        "processing_quantity": 0,
        "pending_qc_quantity": 0,
        "completed_quantity": 0,
        "scrap_quantity": 0,
        "lost_quantity": 0,
    }

def _department(item) -> dict:
    return {
        "department_id": item.id,
        "department_code": item.department_code,
        "department_name": item.department_name,
    }

def _group(items, attribute: str) -> dict:
    grouped = defaultdict(list)
    for item in items:
        grouped[getattr(item, attribute)].append(item)
    return grouped

def _group_rows_by_order(
    rows: list[dict],
    focus_order_id: int | None = None,
) -> list[dict]:
    orders: dict[int, dict] = {}
    for row in rows:
        order_id = row["customer_order_id"]
        group = orders.setdefault(
            order_id,
            {
                "customer_order_id": order_id,
                "customer_order_no": row["customer_order_no"],
                "customer_name": row["customer_name"],
                "order_status": row["order_status"],
                "parts": [],
            },
        )
        group["parts"].append(row)
    grouped = list(orders.values())
    if focus_order_id is not None:
        grouped.sort(
            key=lambda item: item["customer_order_id"] != focus_order_id
        )
    return grouped
