from schemas.engineering import AssemblyNodePayload, PartNodePayload, ProcessFlowPayload


def synchronize_part_metadata(
    flow: ProcessFlowPayload,
    bom_items: dict[int, tuple[str, str]],
    factory_code: str,
) -> ProcessFlowPayload:
    synchronized = flow.model_copy(deep=True)
    for node in synchronized.nodes:
        if isinstance(node, PartNodePayload) and node.bom_item_id in bom_items:
            node.label, node.part_no = bom_items[node.bom_item_id]
    synchronize_assembly_identity(synchronized, factory_code)
    return synchronized


def synchronize_assembly_identity(flow: ProcessFlowPayload, factory_code: str) -> None:
    nodes = {node.id: node for node in flow.nodes}
    incoming: dict[str, list[str]] = {}
    for edge in flow.edges:
        incoming.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    for source_ids in incoming.values():
        source_ids.sort(
            key=lambda node_id: (nodes[node_id].x, nodes[node_id].y, node_id)
        )
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
            node.assembly_name = f"{'-'.join(names)}装配体"
            node.output_name = node.assembly_name
        return names

    for node in flow.nodes:
        component_names(node.id, set())
    assembly_nodes = sorted(
        (node for node in flow.nodes if isinstance(node, AssemblyNodePayload)),
        key=lambda node: (node.x, node.y, node.id),
    )
    for offset, node in enumerate(assembly_nodes):
        node.assembly_sequence = 81 + offset
        node.assembly_code = f"{factory_code}-{node.assembly_sequence}"
        if not node.assembly_name:
            node.assembly_name = "装配体"
            node.output_name = node.assembly_name
