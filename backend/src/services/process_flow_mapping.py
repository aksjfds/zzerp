from schemas.engineering import AssemblyNodePayload, PartNodePayload, ProcessFlowPayload


def synchronize_part_metadata(
    flow: ProcessFlowPayload,
    bom_items: dict[int, tuple[str, str]],
) -> ProcessFlowPayload:
    synchronized = flow.model_copy(deep=True)
    for node in synchronized.nodes:
        if isinstance(node, PartNodePayload) and node.bom_item_id in bom_items:
            node.label, node.part_no = bom_items[node.bom_item_id]
    synchronize_assembly_names(synchronized)
    return synchronized


def synchronize_assembly_names(flow: ProcessFlowPayload) -> None:
    nodes = {node.id: node for node in flow.nodes}
    incoming: dict[str, list[str]] = {}
    for edge in flow.edges:
        incoming.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    cache: dict[str, list[str]] = {}

    def component_names(node_id: str, visiting: set[str]) -> list[str]:
        if node_id in cache:
            return cache[node_id]
        if node_id in visiting:
            return []
        node = nodes.get(node_id)
        if node is None:
            return []
        if isinstance(node, PartNodePayload):
            return [node.label]
        names: list[str] = []
        for source_id in incoming.get(node_id, []):
            for name in component_names(source_id, visiting | {node_id}):
                if name not in names:
                    names.append(name)
        cache[node_id] = names
        if isinstance(node, AssemblyNodePayload) and names:
            node.output_name = f"{'-'.join(names)}装配体"
        return names

    for node in flow.nodes:
        component_names(node.id, set())
