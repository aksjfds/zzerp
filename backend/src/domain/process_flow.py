from collections import defaultdict, deque
from typing import Protocol

from domain.errors import DomainViolation


class FlowNodeLike(Protocol):
    id: str
    type: str
    label: str
    bom_item_id: int


class FlowEdgeLike(Protocol):
    id: str
    source_node_id: str
    target_node_id: str


class ProcessFlowLike(Protocol):
    nodes: list
    edges: list


def validate_process_flow(
    flow: ProcessFlowLike,
    bom_ids: set[int],
) -> ProcessFlowLike:
    if not flow.nodes and not flow.edges:
        return flow
    if not flow.nodes:
        _fail("flow_nodes_missing", "流程图存在连线但没有节点", "process_flow.nodes")

    node_map = {}
    part_node_by_bom: dict[int, str] = {}
    for index, node in enumerate(flow.nodes):
        if node.id in node_map:
            _fail(
                "duplicate_node_id",
                f"流程节点 ID 重复：{node.id}",
                f"process_flow.nodes.{index}.id",
                node.id,
            )
        node_map[node.id] = node
        if node.type == "part":
            if node.bom_item_id not in bom_ids:
                _fail(
                    "invalid_bom_reference",
                    "配件节点未引用当前产品的有效 BOM 行",
                    f"process_flow.nodes.{index}.bom_item_id",
                    node.id,
                )
            if node.bom_item_id in part_node_by_bom:
                _fail(
                    "duplicate_bom_part_node",
                    "同一 BOM 行不能生成多个配件节点",
                    f"process_flow.nodes.{index}.bom_item_id",
                    node.id,
                )
            part_node_by_bom[node.bom_item_id] = node.id

    missing_bom_ids = bom_ids - set(part_node_by_bom)
    if missing_bom_ids:
        _fail(
            "missing_bom_part_nodes",
            "每条 BOM 明细都必须在流程图中有对应配件节点",
            "process_flow.nodes",
        )

    edge_ids: set[str] = set()
    edge_keys: set[tuple[str, str]] = set()
    normal_incoming: dict[str, int] = defaultdict(int)
    normal_outgoing: dict[str, int] = defaultdict(int)
    normal_adjacency: dict[str, list[str]] = defaultdict(list)
    normal_targets: dict[str, list[str]] = defaultdict(list)
    normal_sources: dict[str, list[str]] = defaultdict(list)
    normal_indegree = {node_id: 0 for node_id in node_map}
    undirected: dict[str, set[str]] = defaultdict(set)
    for index, edge in enumerate(flow.edges):
        path = f"process_flow.edges.{index}"
        if edge.id in edge_ids:
            _fail("duplicate_edge_id", f"流程连线 ID 重复：{edge.id}", f"{path}.id", edge.id)
        edge_ids.add(edge.id)
        source = node_map.get(edge.source_node_id)
        target = node_map.get(edge.target_node_id)
        if source is None or target is None:
            _fail("edge_endpoint_missing", "连线引用了不存在的节点", path, edge.id)
        if source.id == target.id:
            _fail("self_loop_not_allowed", "不允许节点连接自身", path, edge.id)
        edge_key = (source.id, target.id)
        if edge_key in edge_keys:
            _fail("duplicate_edge", "相同业务含义的连线不能重复", path, edge.id)
        edge_keys.add(edge_key)
        undirected[source.id].add(target.id)
        undirected[target.id].add(source.id)

        normal_incoming[target.id] += 1
        normal_outgoing[source.id] += 1
        normal_adjacency[source.id].append(target.id)
        normal_targets[source.id].append(target.id)
        normal_sources[target.id].append(source.id)
        normal_indegree[target.id] += 1

    for index, node in enumerate(flow.nodes):
        path = f"process_flow.nodes.{index}"
        if node.type == "part":
            if normal_incoming[node.id] != 0:
                _fail("part_has_incoming_edge", f"配件“{node.label}”不能有输入连线", path, node.id)
            if normal_outgoing[node.id] != 1:
                _fail("part_output_count", f"配件“{node.label}”必须且只能连接一个首节点", path, node.id)
            if node_map[normal_targets[node.id][0]].type not in {"process", "assembly"}:
                _fail(
                    "part_first_node_invalid",
                    "配件节点的第一个执行节点必须是工艺或装配节点",
                    path,
                    node.id,
                )
        elif node.type == "qc":
            if normal_incoming[node.id] != 1:
                _fail("qc_input_count", f"QC节点“{node.label}”必须且只能连接一个上游工艺或装配", path, node.id)
            source = node_map[normal_sources[node.id][0]]
            if source.type not in {"process", "assembly"}:
                _fail("qc_source_invalid", f"QC节点“{node.label}”的上游必须是工艺或装配节点", path, node.id)
            if normal_outgoing[node.id] != 1:
                _fail("qc_output_count", f"QC节点“{node.label}”必须且只能连接一个后续节点", path, node.id)
            target = node_map[normal_targets[node.id][0]]
            if target.type not in {"process", "assembly", "shipping"}:
                _fail("qc_target_invalid", f"QC节点“{node.label}”后只能连接工艺、装配或发货节点", path, node.id)
        elif node.type == "shipping":
            if normal_incoming[node.id] != 1:
                _fail("shipping_input_count", f"发货节点“{node.label}”必须且只能连接一个上游节点", path, node.id)
            if normal_outgoing[node.id] != 0:
                _fail("shipping_has_output", f"发货节点“{node.label}”必须是流程终点，不能再连接后续节点", path, node.id)
        else:
            minimum = 2 if node.type == "assembly" else 1
            if normal_incoming[node.id] < minimum:
                message = (
                    f"装配节点“{node.label}”至少需要两条输入连线"
                    if minimum == 2
                    else f"工艺节点“{node.label}”缺少输入连线"
                )
                _fail("insufficient_normal_inputs", message, path, node.id)
            if node.type == "process" and normal_incoming[node.id] != 1:
                _fail(
                    "process_input_count",
                    f"工艺节点“{node.label}”只能有一个上游；多路配件合并必须使用装配节点",
                    path,
                    node.id,
                )
            if normal_outgoing[node.id] != 1:
                _fail("execution_output_count", f"节点“{node.label}”必须且只能连接一个后续节点", path, node.id)

    _validate_normal_dag(node_map, normal_adjacency, normal_indegree)
    _validate_connected(node_map, undirected)
    return flow


def _validate_normal_dag(node_map, adjacency, indegree) -> None:
    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_map):
        _fail(
            "normal_flow_cycle",
            "宏观工艺路线不能形成环",
            "process_flow.edges",
        )


def _validate_connected(node_map, undirected) -> None:
    first = next(iter(node_map))
    visited = {first}
    queue = deque([first])
    while queue:
        current = queue.popleft()
        for neighbor in undirected[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    if len(visited) != len(node_map):
        _fail("disconnected_flow", "流程图中存在孤立或不连通的节点", "process_flow.nodes")


def _fail(code: str, message: str, path: str, element_id: str | None = None):
    raise DomainViolation(code, message, path, element_id)
