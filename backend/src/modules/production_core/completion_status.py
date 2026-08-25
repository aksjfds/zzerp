"""Project a stable completion status within one material identity."""

from dataclasses import dataclass

from modules.errors import DomainError


EXECUTION_NODE_TYPES = frozenset({"process", "assembly"})


@dataclass(frozen=True, slots=True)
class MaterialCompletionStep:
    flow_node_id: str
    workshop_name: str
    occurrence: int
    completion_status: str
    route_order: int


def material_completion_steps(
    flow: dict,
    nodes: dict[str, dict],
    origin_flow_node_id: str,
) -> tuple[MaterialCompletionStep, ...]:
    """Return execution states from one part/assembly origin to its identity boundary."""
    origin = nodes.get(origin_flow_node_id)
    if origin is None or origin.get("type") not in {"part", "assembly"}:
        raise _projection_error("物料起点不存在或类型无效")

    route_nodes = _material_execution_nodes(flow, nodes, origin)
    occurrences: dict[str, int] = {}
    steps: list[MaterialCompletionStep] = []
    for route_order, node in enumerate(route_nodes):
        workshop_name = str(node.get("label") or "").strip()
        if not workshop_name:
            raise _projection_error("流程中的车间节点缺少名称")
        occurrence = occurrences.get(workshop_name, 0) + 1
        occurrences[workshop_name] = occurrence
        steps.append(MaterialCompletionStep(
            flow_node_id=str(node["id"]),
            workshop_name=workshop_name,
            occurrence=occurrence,
            completion_status=f"{workshop_name}{occurrence}完",
            route_order=route_order,
        ))
    return tuple(steps)


def completed_execution_node_id(
    flow: dict,
    nodes: dict[str, dict],
    completed_flow_node_id: str,
) -> str:
    """Resolve a completed process/assembly node, including a repository sourced from QC."""
    completed = nodes.get(completed_flow_node_id)
    if completed is None:
        raise _projection_error("完成节点不存在")
    if completed.get("type") in EXECUTION_NODE_TYPES:
        return completed_flow_node_id
    if completed.get("type") != "qc":
        raise _projection_error("完成状态必须来自车间节点或其 QC 节点")

    incoming = _incoming_node_ids(flow, completed_flow_node_id)
    if len(incoming) != 1:
        raise _projection_error("无法确定 QC 对应的已完成车间节点")
    source_node_id = incoming[0]
    source = nodes.get(source_node_id)
    if source is None or source.get("type") not in EXECUTION_NODE_TYPES:
        raise _projection_error("QC 上游不是有效的车间节点")
    return source_node_id


def material_completion_status(
    flow: dict,
    nodes: dict[str, dict],
    origin_flow_node_id: str,
    completed_flow_node_id: str,
) -> MaterialCompletionStep:
    execution_node_id = completed_execution_node_id(
        flow,
        nodes,
        completed_flow_node_id,
    )
    for step in material_completion_steps(flow, nodes, origin_flow_node_id):
        if step.flow_node_id == execution_node_id:
            return step
    raise _projection_error("完成节点不属于当前配件或装配体的自身流程")


def _material_execution_nodes(
    flow: dict,
    nodes: dict[str, dict],
    origin: dict,
) -> list[dict]:
    origin_node_id = str(origin["id"])
    origin_is_assembly = origin.get("type") == "assembly"
    if origin_is_assembly:
        current_node_id = origin_node_id
    else:
        current_node_id = _single_target_node_id(flow, nodes, origin_node_id)
        if current_node_id is None:
            raise _projection_error("配件起点没有后续流程节点")
    visited = {origin_node_id} if not origin_is_assembly else set()
    route: list[dict] = []

    while current_node_id is not None:
        if current_node_id in visited:
            raise _projection_error("物料自身流程形成循环")
        visited.add(current_node_id)
        node = nodes.get(current_node_id)
        if node is None:
            raise _projection_error("流程连线引用了不存在的节点")
        node_type = node.get("type")
        if node_type == "shipping":
            break
        if node_type == "assembly" and current_node_id != origin_node_id:
            break
        if node_type in EXECUTION_NODE_TYPES:
            route.append(node)
        elif node_type != "qc":
            raise _projection_error("物料自身流程包含无效节点类型")
        current_node_id = _single_target_node_id(flow, nodes, current_node_id)
        if current_node_id is None:
            raise _projection_error("物料自身流程没有到达装配或成品终点")
    return route


def _single_target_node_id(
    flow: dict,
    nodes: dict[str, dict],
    source_node_id: str,
) -> str | None:
    targets = [
        str(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == source_node_id
        and edge.get("target_node_id")
    ]
    if len(targets) > 1:
        raise _projection_error("物料自身流程存在多个出口")
    if not targets:
        return None
    target_node_id = targets[0]
    if target_node_id not in nodes:
        raise _projection_error("流程连线引用了不存在的节点")
    return target_node_id


def _incoming_node_ids(flow: dict, target_node_id: str) -> list[str]:
    return [
        str(edge.get("source_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == target_node_id
        and edge.get("source_node_id")
    ]


def _projection_error(message: str) -> DomainError:
    return DomainError(
        "material_completion_status_invalid",
        message,
        status_code=409,
    )


__all__ = [
    "MaterialCompletionStep",
    "completed_execution_node_id",
    "material_completion_status",
    "material_completion_steps",
]
