from schemas.engineering import PartNodePayload, ProcessFlowPayload


def synchronize_part_metadata(
    flow: ProcessFlowPayload,
    bom_items: dict[int, tuple[str, str]],
) -> ProcessFlowPayload:
    synchronized = flow.model_copy(deep=True)
    for node in synchronized.nodes:
        if isinstance(node, PartNodePayload) and node.bom_item_id in bom_items:
            node.label, node.part_no = bom_items[node.bom_item_id]
    return synchronized
