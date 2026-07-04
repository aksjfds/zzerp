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
    route_type: str
    outcome: str | None


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

    edge_ids: set[str] = set()
    edge_keys: set[tuple[str, str, str, str | None]] = set()
    normal_incoming: dict[str, int] = defaultdict(int)
    normal_outgoing: dict[str, int] = defaultdict(int)
    normal_adjacency: dict[str, list[str]] = defaultdict(list)
    normal_indegree = {node_id: 0 for node_id in node_map}
    undirected: dict[str, set[str]] = defaultdict(set)
    qc_approved: dict[str, int] = defaultdict(int)
    qc_rework: dict[str, int] = defaultdict(int)
    rework_edges: list[tuple[str, str, str]] = []

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
        edge_key = (source.id, target.id, edge.route_type, edge.outcome)
        if edge_key in edge_keys:
            _fail("duplicate_edge", "相同业务含义的连线不能重复", path, edge.id)
        edge_keys.add(edge_key)
        undirected[source.id].add(target.id)
        undirected[target.id].add(source.id)

        if edge.route_type == "rework":
            if source.type != "qc":
                _fail("rework_source_must_be_qc", "返工连线只能从 QC 节点发出", path, edge.id)
            if target.type not in {"process", "assembly"}:
                _fail("invalid_rework_target", "返工只能返回工序或装配节点", path, edge.id)
            if edge.outcome != "rejected":
                _fail("invalid_rework_outcome", "返工连线必须标记为 rejected", path, edge.id)
            qc_rework[source.id] += 1
            rework_edges.append((edge.id, source.id, target.id))
        else:
            if source.type == "qc":
                if edge.outcome != "approved":
                    _fail("invalid_qc_approved_edge", "QC 正常出口必须标记为 approved", path, edge.id)
                qc_approved[source.id] += 1
            elif edge.outcome is not None:
                _fail("outcome_only_for_qc", "只有 QC 连线可以设置 outcome", path, edge.id)
            normal_incoming[target.id] += 1
            normal_outgoing[source.id] += 1
            normal_adjacency[source.id].append(target.id)
            normal_indegree[target.id] += 1

    for index, node in enumerate(flow.nodes):
        path = f"process_flow.nodes.{index}"
        if node.type == "part":
            if normal_incoming[node.id] != 0:
                _fail("part_has_incoming_edge", "配件节点不能有普通输入连线", path, node.id)
            if normal_outgoing[node.id] == 0:
                _fail("part_has_no_output", "配件节点必须连接后续工序或装配", path, node.id)
        else:
            minimum = 2 if node.type == "assembly" else 1
            if normal_incoming[node.id] < minimum:
                message = "装配节点至少需要两条普通输入连线" if minimum == 2 else "节点缺少普通输入连线"
                _fail("insufficient_normal_inputs", message, path, node.id)
        if node.type == "qc":
            if qc_approved[node.id] != 1:
                _fail("qc_approved_edge_count", "QC 节点必须且只能有一条合格出口", path, node.id)
            if qc_rework[node.id] > 1:
                _fail("qc_rework_edge_count", "QC 节点最多只能有一条返工出口", path, node.id)

    _validate_normal_dag(node_map, normal_adjacency, normal_indegree)
    _validate_connected(node_map, undirected)
    for edge_id, qc_id, target_id in rework_edges:
        if not _can_reach(target_id, qc_id, normal_adjacency):
            _fail(
                "rework_target_not_before_qc",
                "返工目标必须能沿正常路线重新到达当前 QC 节点",
                "process_flow.edges",
                edge_id,
            )
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
            "普通工艺路线不能形成环；循环只能使用 QC 返工连线",
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


def _can_reach(start: str, target: str, adjacency) -> bool:
    queue = deque([start])
    visited = {start}
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


def _fail(code: str, message: str, path: str, element_id: str | None = None):
    raise DomainViolation(code, message, path, element_id)
