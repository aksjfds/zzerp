"""Response assembly for production-workbench positions."""

from datetime import datetime

from sqlalchemy import select

from domain.material_identity import production_item_material_key
from domain.time import business_iso
from modules.organization.model_api import Department
from modules.planning.production_workbench_candidates import (
    _assembly_availability,
    _assembly_identity,
    _assembly_output_item_id,
    _input_unit_quantity,
    _procedure_scope,
    _production_item_identity,
    _require_item,
)
from modules.planning.production_workbench_queries import _arrival_times
from modules.planning.production_workbench_types import (
    AssemblyCandidate,
    CandidateView,
    DisplayData,
    StandardCandidate,
)
from modules.production_core.model_api import MaterialProcessingState, ProductionItem, Repository
from modules.production_core.workbench_read_api import PositionActivity
from modules.standard_execution.configuration_api import (
    ConfiguredProcedure,
    ProcedureConfigurationScope,
    list_confirmed_procedures,
)


def _serialize_page(
    session,
    selected: list[CandidateView],
    display: DisplayData,
    department: Department,
    reservation_by_id: dict[int, int],
) -> list[dict]:
    processing_state_ids = {
        repository.processing_state_id
        for view in selected
        for repository in view.candidate.repositories
    }
    processing_states = {
        state.id: state
        for state in session.scalars(
            select(MaterialProcessingState).where(
                MaterialProcessingState.id.in_(processing_state_ids)
            )
        )
    } if processing_state_ids else {}
    arrivals = _arrival_times(session, selected, display, department.id)
    scopes = {
        _procedure_scope(view, display)
        for view in selected
    }
    configured = list_confirmed_procedures(session, scopes)
    result = []
    for view in selected:
        if view.position_type == "standard":
            result.append(_serialize_standard(
                view,
                display,
                department,
                reservation_by_id,
                processing_states,
                arrivals,
                configured,
            ))
        else:
            result.append(_serialize_assembly(
                view,
                display,
                department,
                reservation_by_id,
                processing_states,
                arrivals,
                configured,
            ))
    return result


def _serialize_standard(
    view: CandidateView,
    display: DisplayData,
    department: Department,
    reservation_by_id: dict[int, int],
    processing_states: dict[int, MaterialProcessingState],
    arrivals: dict[tuple, datetime],
    configured: dict[ProcedureConfigurationScope, list[ConfiguredProcedure]],
) -> dict:
    candidate = view.candidate
    assert isinstance(candidate, StandardCandidate)
    item = _require_item(display, view.representative_item_id)
    context = display.contexts[item.id]
    source_node = context.nodes.get(candidate.key[2], {})
    scope = _procedure_scope(view, display)
    configured_procedures = configured.get(scope, [])
    arrived_at = arrivals.get(("standard", *candidate.key))
    sources = []
    for repository in candidate.repositories:
        reserved = reservation_by_id.get(repository.id, 0)
        available = max(repository.quantity - reserved, 0)
        completed_procedure_ids = {
            history.get("procedure_id")
            for history in processing_states[repository.processing_state_id].procedure_history
            if history.get("flow_node_id") == repository.flow_node_id
        }
        procedures = [
            procedure
            for procedure in configured_procedures
            if procedure.id not in completed_procedure_ids
        ]
        sources.append({
            "repository_id": repository.id,
            "production_item_id": repository.production_item_id,
            "source_work_order_id": repository.source_work_order_id,
            "processing_status": processing_states[repository.processing_state_id].display_text,
            "on_hand_quantity": repository.quantity,
            "reserved_quantity": reserved,
            "available_quantity": available,
            "arrived_at": business_iso(arrived_at),
            "available_procedures": [
                _configured_procedure_response(procedure)
                for procedure in procedures
            ],
            "procedure_configuration_confirmed": scope in configured,
            "can_create_work_order": scope in configured and available > 0,
        })
    common = _common_position(
        view,
        display,
        department,
        item,
        source_flow_node_id=candidate.key[2],
        source_node_label=str(source_node.get("label") or "未知来源"),
        arrived_at=arrived_at,
    )
    return {
        **common,
        "position_type": "standard",
        "on_hand_quantity": sum(item["on_hand_quantity"] for item in sources),
        "reserved_quantity": sum(item["reserved_quantity"] for item in sources),
        "available_quantity": sum(item["available_quantity"] for item in sources),
        "source_count": len(sources),
        "sources": sources,
        "can_create_work_order": any(item["can_create_work_order"] for item in sources),
    }


def _serialize_assembly(
    view: CandidateView,
    display: DisplayData,
    department: Department,
    reservation_by_id: dict[int, int],
    processing_states: dict[int, MaterialProcessingState],
    arrivals: dict[tuple, datetime],
    configured: dict[ProcedureConfigurationScope, list[ConfiguredProcedure]],
) -> dict:
    candidate = view.candidate
    assert isinstance(candidate, AssemblyCandidate)
    item = _require_item(display, view.representative_item_id)
    arrived_at = arrivals.get(("assembly", *candidate.key))
    scope = _procedure_scope(view, display)
    configured_procedures = configured.get(scope, [])
    availability = _assembly_availability(candidate, display, reservation_by_id)
    input_materials = _assembly_input_materials(
        candidate,
        display,
        reservation_by_id,
        arrived_at,
        availability.required_material_keys,
        processing_states,
    )
    continuation_sources = _assembly_continuation_sources(
        candidate,
        display,
        reservation_by_id,
        processing_states,
        arrived_at,
        configured_procedures,
        scope in configured,
    )
    common = _common_position(
        view,
        display,
        department,
        item,
        source_flow_node_id=None,
        source_node_label=None,
        arrived_at=arrived_at,
    )
    return {
        **common,
        "position_type": "assembly",
        "production_item_id": _assembly_output_item_id(candidate, display),
        "capacity_quantity": availability.capacity_quantity,
        "initial_capacity_quantity": availability.initial_capacity_quantity,
        "continuation_capacity_quantity": availability.continuation_capacity_quantity,
        "input_materials_complete": availability.input_materials_complete,
        "can_create_initial_work_order": (
            availability.input_materials_complete
            and availability.initial_capacity_quantity > 0
            and scope in configured
        ),
        "input_material_count": len(availability.required_material_keys),
        "input_materials": input_materials,
        "continuation_sources": continuation_sources,
        "available_procedures": [
            _configured_procedure_response(procedure)
            for procedure in configured_procedures
        ],
        "procedure_configuration_confirmed": scope in configured,
        "can_create_work_order": (
            (
                availability.input_materials_complete
                and availability.initial_capacity_quantity > 0
                and scope in configured
            )
            or any(source["can_create_work_order"] for source in continuation_sources)
        ),
    }


def _assembly_continuation_sources(
    candidate: AssemblyCandidate,
    display: DisplayData,
    reservation_by_id: dict[int, int],
    processing_states: dict[int, MaterialProcessingState],
    arrived_at: datetime | None,
    configured_procedures: list[ConfiguredProcedure],
    configuration_confirmed: bool,
) -> list[dict]:
    continuation_key = f"assembly:{candidate.key[1]}"
    sources = []
    for repository in candidate.repositories:
        item = _require_item(display, repository.production_item_id)
        if production_item_material_key(item) != continuation_key:
            continue
        completed_procedure_ids = {
            history.get("procedure_id")
            for history in processing_states[repository.processing_state_id].procedure_history
            if history.get("flow_node_id") == candidate.key[1]
        }
        procedures = [
            procedure
            for procedure in configured_procedures
            if procedure.id not in completed_procedure_ids
        ]
        reserved = reservation_by_id.get(repository.id, 0)
        available = max(repository.quantity - reserved, 0)
        sources.append({
            "repository_id": repository.id,
            "production_item_id": repository.production_item_id,
            "source_work_order_id": repository.source_work_order_id,
            "processing_status": processing_states[repository.processing_state_id].display_text,
            "on_hand_quantity": repository.quantity,
            "reserved_quantity": reserved,
            "available_quantity": available,
            "arrived_at": business_iso(arrived_at),
            "available_procedures": [
                _configured_procedure_response(procedure)
                for procedure in procedures
            ],
            "procedure_configuration_confirmed": configuration_confirmed,
            "can_create_work_order": configuration_confirmed and available > 0,
        })
    return sources


def _common_position(
    view: CandidateView,
    display: DisplayData,
    department: Department,
    item: ProductionItem,
    *,
    source_flow_node_id: str | None,
    source_node_label: str | None,
    arrived_at: datetime | None,
) -> dict:
    context = display.contexts[item.id]
    order_item = context.order_item
    order = display.orders[order_item.customer_order_id]
    customer = display.customers[order.customer_id]
    product = display.products[item.product_id]
    item_code, item_name = _production_item_identity(item, context)
    if view.position_type == "assembly":
        item_code, item_name = _assembly_identity(view.node)
    activity = view.candidate.activity
    last_activity = max(
        (timestamp for timestamp in (arrived_at, activity.last_activity_at) if timestamp),
        default=None,
    )
    return {
        "position_key": view.position_key,
        "production_item_id": item.id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": customer.customer_name,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "factory_code": product.factory_code,
        "product_name": product.product_name,
        "item_code": item_code,
        "item_name": item_name,
        "flow_node_id": view.node["id"],
        "source_flow_node_id": source_flow_node_id,
        "source_node_label": source_node_label,
        "node_type": view.node["type"],
        "workshop_id": view.workshop.id,
        "workshop_name": view.workshop.workshop_name,
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "delivery_date": order_item.delivery_date,
        "arrived_at": business_iso(arrived_at),
        "last_activity_at": business_iso(last_activity),
        "activity": _activity_response(activity),
        "can_create_work_order": False,
    }


def _assembly_input_materials(
    candidate: AssemblyCandidate,
    display: DisplayData,
    reservation_by_id: dict[int, int],
    arrived_at: datetime | None,
    required_material_keys: frozenset[str],
    processing_states: dict[int, MaterialProcessingState],
) -> list[dict]:
    repositories_by_key: dict[str, list[Repository]] = {}
    item_by_key: dict[str, ProductionItem] = {}
    for item in display.items.values():
        if item.customer_order_item_id != candidate.key[0]:
            continue
        key = production_item_material_key(item)
        if key in required_material_keys:
            item_by_key.setdefault(key, item)
    for repository in candidate.repositories:
        item = _require_item(display, repository.production_item_id)
        key = production_item_material_key(item)
        if key not in required_material_keys:
            continue
        repositories_by_key.setdefault(key, []).append(repository)
        item_by_key.setdefault(key, item)
    allocated_by_key: dict[str, int] = {}
    for allocation in candidate.allocations:
        item = _require_item(display, allocation.production_item_id)
        key = production_item_material_key(item)
        if key not in required_material_keys:
            continue
        item_by_key.setdefault(key, item)
        allocated_by_key[key] = allocated_by_key.get(key, 0) + allocation.quantity
    result = []
    for key in sorted(item_by_key):
        item = item_by_key[key]
        context = display.contexts[item.id]
        item_code, item_name = _production_item_identity(item, context)
        unit_quantity = _input_unit_quantity(item, context, candidate.key[1])
        sources = []
        for repository in repositories_by_key.get(key, []):
            reserved = reservation_by_id.get(repository.id, 0)
            sources.append({
                "repository_id": repository.id,
                "production_item_id": repository.production_item_id,
                "source_work_order_id": repository.source_work_order_id,
                "processing_status": processing_states[repository.processing_state_id].display_text,
                "on_hand_quantity": repository.quantity,
                "reserved_quantity": reserved,
                "available_quantity": max(repository.quantity - reserved, 0),
                "arrived_at": business_iso(arrived_at),
            })
        result.append({
            "material_key": key,
            "item_code": item_code,
            "item_name": item_name,
            "unit_quantity": unit_quantity,
            "on_hand_quantity": sum(source["on_hand_quantity"] for source in sources),
            "reserved_quantity": sum(source["reserved_quantity"] for source in sources),
            "available_quantity": sum(source["available_quantity"] for source in sources),
            "allocated_quantity": allocated_by_key.get(key, 0),
            "sources": sources,
        })
    return result


def _activity_response(activity: PositionActivity) -> dict:
    return {
        "open_work_order_count": activity.open_work_order_count,
        "processing_work_order_count": activity.processing_work_order_count,
        "ready_for_result_work_order_count": (
            activity.ready_for_result_work_order_count
        ),
        "pending_qc_work_order_count": activity.pending_qc_work_order_count,
        "rework_work_order_count": activity.rework_work_order_count,
    }


def _configured_procedure_response(procedure: ConfiguredProcedure) -> dict:
    return {
        "id": procedure.id,
        "workshop_id": procedure.workshop_id,
        "department_name": procedure.department_name,
        "department_code": procedure.department_code,
        "procedure_name": procedure.procedure_name,
    }
