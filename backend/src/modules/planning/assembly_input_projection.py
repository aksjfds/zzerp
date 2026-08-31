"""Project the stable material identities required by a multi-input node."""

from modules.production_core.flow_api import assembly_material_key


def normal_input_material_keys(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> list[str]:
    source_node_ids = dict.fromkeys(
        edge["source_node_id"]
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
        and edge.get("source_node_id")
    )
    return list(dict.fromkeys(
        key
        for source_node_id in source_node_ids
        if (
            key := assembly_material_key(
                flow,
                nodes,
                source_node_id,
            )
        ) is not None
    ))
