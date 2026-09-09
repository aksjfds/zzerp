"""Candidate position and availability calculations for the workbench."""

from hashlib import sha256
import json

from domain.material_identity import production_item_material_key
from modules.errors import DomainError
from modules.organization.model_api import Department, Workshop
from modules.planning.assembly_input_projection import normal_input_material_keys
from modules.planning.production_workbench_types import (
    AssemblyAvailability,
    AssemblyCandidate,
    AssemblyKey,
    CandidateView,
    DisplayData,
    StandardCandidate,
    StandardKey,
)
from modules.production_core.flow_api import ProductionFlowContext
from modules.production_core.model_api import ProductionItem, Repository
from modules.production_core.workbench_read_api import AssemblyInputAllocation, PositionActivity


def _group_candidates(
    repositories: list[Repository],
    standard_activity: dict[StandardKey, PositionActivity],
    assembly_activity: dict[AssemblyKey, PositionActivity],
    allocations: tuple[AssemblyInputAllocation, ...],
    display: DisplayData,
) -> tuple[dict[StandardKey, StandardCandidate], dict[AssemblyKey, AssemblyCandidate]]:
    standard: dict[StandardKey, StandardCandidate] = {}
    assembly: dict[AssemblyKey, AssemblyCandidate] = {}
    for repository in repositories:
        item = _require_item(display, repository.production_item_id)
        context = display.contexts[item.id]
        node = _require_node(context.nodes, repository.flow_node_id)
        if node.get("type") == "assembly":
            key = (item.customer_order_item_id, repository.flow_node_id)
            candidate = assembly.setdefault(key, AssemblyCandidate(key=key))
            candidate.production_item_ids.add(item.id)
            candidate.repositories.append(repository)
        else:
            key = (
                repository.production_item_id,
                repository.flow_node_id,
                repository.source_flow_node_id,
            )
            standard.setdefault(key, StandardCandidate(key=key)).repositories.append(
                repository
            )
    for key, position_activity in standard_activity.items():
        candidate = standard.setdefault(key, StandardCandidate(key=key))
        candidate.activity = position_activity
    for key, position_activity in assembly_activity.items():
        candidate = assembly.setdefault(key, AssemblyCandidate(key=key))
        candidate.activity = position_activity
        candidate.production_item_ids.update(position_activity.production_item_ids)
    for allocation in allocations:
        key = (allocation.customer_order_item_id, allocation.flow_node_id)
        candidate = assembly.setdefault(key, AssemblyCandidate(key=key))
        candidate.production_item_ids.add(allocation.production_item_id)
        candidate.allocations.append(allocation)
    return standard, assembly


def _candidate_views(
    standard: dict[StandardKey, StandardCandidate],
    assembly: dict[AssemblyKey, AssemblyCandidate],
    display: DisplayData,
    department: Department,
    reservation_by_id: dict[int, int],
) -> list[CandidateView]:
    views: list[CandidateView] = []
    for key, candidate in standard.items():
        item = _require_item(display, key[0])
        context = display.contexts[item.id]
        node = _require_node(context.nodes, key[1])
        workshop = _require_workshop(display, node, department.id)
        available = sum(
            max(repository.quantity - reservation_by_id.get(repository.id, 0), 0)
            for repository in candidate.repositories
        )
        views.append(CandidateView(
            candidate=candidate,
            position_type="standard",
            position_key=_position_key("standard", department.department_code, *key),
            representative_item_id=item.id,
            customer_order_item_id=item.customer_order_item_id,
            node=node,
            workshop=workshop,
            available_quantity=available,
        ))
    for key, candidate in assembly.items():
        representative_id = _assembly_representative_id(candidate, display)
        item = _require_item(display, representative_id)
        context = display.contexts[item.id]
        node = _require_node(context.nodes, key[1])
        workshop = _require_workshop(display, node, department.id)
        availability = _assembly_availability(
            candidate,
            display,
            reservation_by_id,
        )
        views.append(CandidateView(
            candidate=candidate,
            position_type="assembly",
            position_key=_position_key("assembly", department.department_code, *key),
            representative_item_id=representative_id,
            customer_order_item_id=key[0],
            node=node,
            workshop=workshop,
            available_quantity=availability.capacity_quantity,
        ))
    return views


def _filter_candidates(
    candidates: list[CandidateView],
    workshop_id: int,
    customer_order_item_id: int,
    production_item_id: int | None,
    flow_node_id: str,
) -> list[CandidateView]:
    result = []
    for view in candidates:
        if view.customer_order_item_id != customer_order_item_id:
            continue
        if (
            production_item_id is not None
            and view.representative_item_id != production_item_id
        ):
            continue
        if view.node["id"] != flow_node_id:
            continue
        if view.workshop.id != workshop_id:
            continue
        result.append(view)
    return result


def _candidate_sort_key(view: CandidateView):
    activity = view.candidate.activity
    return (
        activity.rework_work_order_count > 0,
        activity.pending_qc_work_order_count > 0,
        activity.ready_for_result_work_order_count > 0,
        activity.processing_work_order_count > 0,
        view.available_quantity > 0,
        activity.last_activity_at.timestamp() if activity.last_activity_at else 0.0,
        view.position_key,
    )


def _assembly_availability(
    candidate: AssemblyCandidate,
    display: DisplayData,
    reservation_by_id: dict[int, int],
) -> AssemblyAvailability:
    representative = _require_item(display, _assembly_representative_id(candidate, display))
    context = display.contexts[representative.id]
    required = set(normal_input_material_keys(
        context.flow,
        context.nodes,
        candidate.key[1],
    ))
    available_by_key: dict[str, int] = {}
    unit_by_key: dict[str, int] = {}
    for repository in candidate.repositories:
        item = _require_item(display, repository.production_item_id)
        key = production_item_material_key(item)
        available_by_key[key] = available_by_key.get(key, 0) + max(
            repository.quantity - reservation_by_id.get(repository.id, 0),
            0,
        )
        unit_by_key[key] = _input_unit_quantity(
            item,
            display.contexts[item.id],
            candidate.key[1],
        )
    initial_complete = bool(required) and required.issubset(available_by_key)
    initial_capacity = (
        min(
            available_by_key[key] // max(unit_by_key.get(key, 1), 1)
            for key in required
        )
        if initial_complete else 0
    )
    continuation_key = f"assembly:{candidate.key[1]}"
    continuation_capacities = [
        max(
            repository.quantity - reservation_by_id.get(repository.id, 0),
            0,
        )
        for repository in candidate.repositories
        if production_item_material_key(
            _require_item(display, repository.production_item_id)
        ) == continuation_key
    ]
    capacity = max([initial_capacity, *continuation_capacities])
    return AssemblyAvailability(
        capacity_quantity=capacity,
        initial_capacity_quantity=initial_capacity,
        continuation_capacity_quantity=max(continuation_capacities, default=0),
        input_materials_complete=initial_complete,
        required_material_keys=frozenset(required),
    )


def _procedure_scope(view: CandidateView, display: DisplayData):
    item = _require_item(display, view.representative_item_id)
    material_key = (
        f"assembly:{view.node['id']}"
        if view.position_type == "assembly"
        else production_item_material_key(item)
    )
    return (
        item.product_id,
        item.product_version,
        material_key,
        view.node["id"],
    )


def _assembly_representative_id(
    candidate: AssemblyCandidate,
    display: DisplayData,
) -> int:
    output_ids = [
        item_id
        for item_id in candidate.production_item_ids
        if (item := display.items.get(item_id)) is not None
        and item.product_bom_id is None
        and item.origin_flow_node_id == candidate.key[1]
    ]
    if output_ids:
        return min(output_ids)
    if candidate.production_item_ids:
        return min(candidate.production_item_ids)
    raise DomainError("production_context_missing", "装配任务缺少生产项")


def _assembly_output_item_id(
    candidate: AssemblyCandidate,
    display: DisplayData,
) -> int | None:
    output_ids = [
        item_id
        for item_id in candidate.production_item_ids
        if (item := display.items.get(item_id)) is not None
        and item.product_bom_id is None
        and item.origin_flow_node_id == candidate.key[1]
    ]
    return min(output_ids) if output_ids else None


def _input_unit_quantity(item: ProductionItem, context, assembly_node_id: str) -> int:
    if item.product_bom_id is not None and context.bom_item is not None:
        return max(int(context.bom_item.pcs), 1)
    if item.origin_flow_node_id == assembly_node_id:
        return 1
    origin = context.nodes.get(item.origin_flow_node_id, {})
    return max(int(origin.get("output_pcs") or 1), 1)


def _production_item_identity(
    item: ProductionItem,
    context: ProductionFlowContext,
) -> tuple[str, str]:
    if item.product_bom_id is not None:
        return context.item_name(item)
    return _assembly_identity(context.nodes.get(item.origin_flow_node_id, {}))


def _assembly_identity(node: dict) -> tuple[str, str]:
    name = str(
        node.get("assembly_name")
        or node.get("output_name")
        or node.get("label")
        or "装配体"
    )
    code = str(node.get("assembly_code") or name)
    return code, name


def _position_key(position_type: str, department_code: str, *identity) -> str:
    payload = json.dumps(
        [position_type, department_code, *identity],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"{position_type}:{sha256(payload.encode('utf-8')).hexdigest()}"


def _require_item(display: DisplayData, item_id: int) -> ProductionItem:
    item = display.items.get(item_id)
    if item is None:
        raise DomainError("production_context_missing", "生产项不存在")
    return item


def _require_node(nodes: dict[str, dict], node_id: str) -> dict:
    node = nodes.get(node_id)
    if node is None:
        raise DomainError("flow_node_missing", "当前流程节点不存在")
    return node


def _require_workshop(
    display: DisplayData,
    node: dict,
    department_id: int,
) -> Workshop:
    workshop = display.workshops.get(node.get("workshop_id"))
    if workshop is None or workshop.department_id != department_id:
        raise DomainError("workshop_department_missing", "当前节点不属于所选部门")
    return workshop
