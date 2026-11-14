"""Stable graph order through strongly connected components and their DAG."""

from heapq import heappop, heappush

from zzerp.modules.engineering.flow import flow_adjacency, validate_process_flow


def _finish_order(positions, outgoing):
    visited, finished = set(), []
    for start in positions:
        stack = [(start, False)]
        while stack:
            key, expanded = stack.pop()
            if expanded:
                finished.append(key)
            elif key not in visited:
                visited.add(key)
                stack.append((key, True))
                stack.extend(
                    (target, False)
                    for target in sorted(outgoing[key], key=positions.get, reverse=True)
                    if target not in visited
                )
    return finished


def _connected_groups(positions, incoming, outgoing):
    groups, membership = [], {}
    for start in reversed(_finish_order(positions, outgoing)):
        if start in membership:
            continue
        group = set()
        stack = [start]
        membership[start] = len(groups)
        while stack:
            key = stack.pop()
            group.add(key)
            for source in incoming[key]:
                if source not in membership:
                    membership[source] = len(groups)
                    stack.append(source)
        groups.append(group)
    return groups, membership


def _component_order(groups, membership, outgoing, positions):
    successors = {index: set() for index in range(len(groups))}
    indegrees = dict.fromkeys(successors, 0)
    for source, targets in outgoing.items():
        for target in targets:
            left, right = membership[source], membership[target]
            if left != right and right not in successors[left]:
                successors[left].add(right)
                indegrees[right] += 1
    priorities = {index: min(positions[key] for key in group) for index, group in enumerate(groups)}
    pending = []
    for index, degree in indegrees.items():
        if not degree:
            heappush(pending, (priorities[index], index))
    ordered = []
    while pending:
        _, index = heappop(pending)
        ordered.append(index)
        for target in successors[index]:
            indegrees[target] -= 1
            if not indegrees[target]:
                heappush(pending, (priorities[target], target))
    return ordered


def _group_nodes(group, incoming, outgoing, positions):
    entries = sorted(
        (key for key in group if incoming[key] - group),
        key=positions.get,
    )
    seen, ordered = set(), []
    for start in entries + sorted(group, key=positions.get):
        stack = [start]
        while stack:
            key = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
            stack.extend(sorted(outgoing[key] & group, key=positions.get, reverse=True))
    return ordered


def department_route_order(flow) -> dict[str, int]:
    validate_process_flow(flow)
    positions = {node.id: index for index, node in enumerate(flow.nodes)}
    incoming, outgoing = flow_adjacency(flow)
    groups, membership = _connected_groups(positions, incoming, outgoing)
    ordered = []
    for index in _component_order(groups, membership, outgoing, positions):
        ordered.extend(_group_nodes(groups[index], incoming, outgoing, positions))
    departments = {node.id for node in flow.nodes if node.type == "department"}
    return {key: index for index, key in enumerate(key for key in ordered if key in departments)}
