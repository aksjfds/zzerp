from __future__ import annotations

"""Shared production-card material and workshop mapping."""

from modules.production_core.flow_api import assembly_material_key

def _workshop_procedures(
    procedure_views,
    workshop_id: int | None,
    procedure_type: str,
    input_mode: str,
):
    if workshop_id is None:
        return []
    return procedure_views.get((workshop_id, procedure_type, input_mode), [])

def _material_source_name(context, production_item) -> str:
    current_id = production_item.origin_flow_node_id
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        target = context.normal_target(current_id)
        if target is None:
            break
        if target.get("type") == "process":
            return str(target.get("label") or "路线")
        if target.get("type") in {"assembly", "shipping"}:
            break
        current_id = str(target.get("id") or "")
    return "装配体" if production_item.product_bom_id is None else "直接来源"

def _normal_input_source_ids(flow: dict, node_id: str) -> list[str]:
    return list(dict.fromkeys(
        edge["source_node_id"]
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
        and edge.get("source_node_id")
    ))

def _normal_input_material_keys(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> list[str]:
    return list(dict.fromkeys(
        key
        for source_id in _normal_input_source_ids(flow, node_id)
        if (key := assembly_material_key(flow, nodes, source_id)) is not None
    ))
