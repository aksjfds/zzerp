from __future__ import annotations

from collections import defaultdict
from math import ceil

from modules.engineering.model_api import ProductBom
from modules.production_core.flow import assembly_material_key
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    WorkOrder,
)
from modules.production_core.operational_api import (
    calculate_assembly_output_progress,
)
from modules.quality.model_api import WorkOrderBatch


def assembly_arrived_output_quantity(
    flow: dict,
    nodes: dict[str, dict],
    assembly_node_id: str,
    output_unit_quantity: int,
    production_items: list[ProductionItem],
    movements: list[ProductionMovement],
    bom_items: dict[int, ProductBom],
) -> int:
    """Convert all materials received by an assembly node into complete outputs."""
    arrived_quantity, _ = assembly_arrival_progress(
        flow,
        nodes,
        assembly_node_id,
        output_unit_quantity,
        production_items,
        movements,
        bom_items,
        task_quantity=0,
    )
    return arrived_quantity


def assembly_arrival_progress(
    flow: dict,
    nodes: dict[str, dict],
    assembly_node_id: str,
    output_unit_quantity: int,
    production_items: list[ProductionItem],
    movements: list[ProductionMovement],
    bom_items: dict[int, ProductBom],
    task_quantity: int,
) -> tuple[int, list[dict]]:
    required_materials: dict[str, dict] = {}
    for edge in flow.get("edges", []):
        if edge.get("target_node_id") != assembly_node_id:
            continue
        source_node_id = edge.get("source_node_id")
        material_key = (
            assembly_material_key(flow, nodes, source_node_id)
            if source_node_id else None
        )
        if material_key is None:
            continue
        if material_key.startswith("part:"):
            bom_item = bom_items.get(int(material_key.removeprefix("part:")))
            unit_quantity = bom_item.pcs if bom_item else 0
            material_type = "part"
            material_no = bom_item.part_no if bom_item else ""
            material_name = bom_item.part_name if bom_item else ""
        else:
            source_node = nodes.get(material_key.removeprefix("assembly:"), {})
            unit_quantity = int(source_node.get("output_pcs") or 1)
            material_type = "assembly"
            material_no = str(
                source_node.get("assembly_code")
                or source_node.get("id")
                or ""
            )
            material_name = str(
                source_node.get("assembly_name")
                or source_node.get("output_name")
                or source_node.get("label")
                or "装配体"
            )
        if unit_quantity > 0:
            required_materials[material_key] = {
                "material_type": material_type,
                "material_no": material_no,
                "material_name": material_name,
                "unit_quantity": unit_quantity,
            }
    if not required_materials:
        return 0, []

    material_key_by_item = {
        item.id: (
            f"part:{item.product_bom_id}"
            if item.product_bom_id is not None
            else f"assembly:{item.origin_flow_node_id}"
        )
        for item in production_items
    }
    arrived_by_material: dict[str, int] = defaultdict(int)
    for movement in movements:
        if (
            movement.target_flow_node_id != assembly_node_id
            or movement.source_flow_node_id == movement.target_flow_node_id
        ):
            continue
        material_key = material_key_by_item.get(movement.production_item_id)
        if material_key in required_materials:
            arrived_by_material[material_key] += movement.quantity
    complete_products = min(
        arrived_by_material.get(material_key, 0) // material["unit_quantity"]
        for material_key, material in required_materials.items()
    )
    output_quantity = max(int(output_unit_quantity), 1)
    task_products = ceil(task_quantity / output_quantity) if task_quantity else 0
    details = []
    for material_key, material in required_materials.items():
        material_task_quantity = task_products * material["unit_quantity"]
        arrived_material_quantity = arrived_by_material.get(material_key, 0)
        details.append({
            "material_type": material["material_type"],
            "material_no": material["material_no"],
            "material_name": material["material_name"],
            "task_quantity": material_task_quantity,
            "arrived_quantity": arrived_material_quantity,
        })
    return complete_products * output_quantity, details


def assembly_completion_summary(
    work_orders: list[WorkOrder],
    batches_by_order: dict[int, list[WorkOrderBatch]],
    output_unit_quantity: int,
) -> int:
    completed_quantity = 0
    for work_order in work_orders:
        batches = batches_by_order.get(work_order.id, [])
        progress = calculate_assembly_output_progress(
            work_order,
            batches,
            output_unit_quantity,
        )
        completed_quantity += progress.qualified_quantity

    return completed_quantity


__all__ = [
    "assembly_arrival_progress",
    "assembly_arrived_output_quantity",
    "assembly_completion_summary",
]
