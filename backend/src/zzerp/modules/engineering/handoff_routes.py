"""Direct transfer destinations from engineering."""

from collections import defaultdict

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import HandoffRoutes
from zzerp.modules.engineering.flow import material_routes


def resolve_handoff_routes(flow) -> HandoffRoutes:
    routes = material_routes(flow)
    nodes = {node.id: node for node in flow.nodes}
    by_department = defaultdict(list)
    for route in routes:
        by_department[route.department_node_id].append(route)
    successors = {(route.material_node_id, route.department_node_id): set() for route in routes}
    for edge in flow.edges:
        if nodes[edge.source_node_id].type == "part":
            continue
        for source in by_department[edge.source_node_id]:
            for target in by_department[edge.target_node_id]:
                same_material = source.material_node_id == target.material_node_id
                merges_input = target.material_node_id == target.department_node_id and set(
                    source.part_node_ids
                ) <= set(target.part_node_ids)
                if same_material or merges_input:
                    successors[(source.material_node_id, source.department_node_id)].add(
                        (target.material_node_id, target.department_node_id)
                    )
    return HandoffRoutes({key: frozenset(value) for key, value in successors.items()})


def ensure_handoffs_preserved(flow, referenced_pairs):
    routes = resolve_handoff_routes(flow)
    if any(
        (tm, td) not in routes.successors.get((sm, sd), frozenset())
        for sm, sd, tm, td in referenced_pairs
    ):
        raise DomainError(
            "handoff_route_in_use", "路线已有交接票，不能断开来源与目标的直接关系", status_code=409
        )
