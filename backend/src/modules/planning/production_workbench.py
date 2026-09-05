"""Department production-workbench position read model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json

from sqlalchemy import select, tuple_

from database import SessionLocal
from domain.material_identity import production_item_material_key
from domain.time import business_iso
from modules.engineering.model_api import (
    Product,
    ProductBom,
    ProductProcessFlow,
)
from modules.errors import DomainError
from modules.organization.model_api import Department, Workshop
from modules.planning.assembly_input_projection import normal_input_material_keys
from modules.planning.persistence import ProductionPlan
from modules.production_core.flow_api import ProductionFlowContext, load_production_flow
from modules.production_core.model_api import (
    MaterialProcessingState,
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.operational_api import ProductionItemDisplayContext
from modules.production_core.workbench_read_api import (
    AssemblyInputAllocation,
    PositionActivity,
    load_workbench_activity,
    reserved_quantities,
)
from modules.sales.model_api import (
    Customer,
    CustomerOrder,
    CustomerOrderItem,
)
from modules.standard_execution.configuration_api import (
    ConfiguredProcedure,
    ProcedureConfigurationScope,
    list_confirmed_procedures,
)


StandardKey = tuple[int, str, str]
AssemblyKey = tuple[int, str]
@dataclass(slots=True)
class DisplayData:
    items: dict[int, ProductionItem]
    orders: dict[int, CustomerOrder]
    customers: dict[int, Customer]
    products: dict[int, Product]
    contexts: dict[int, ProductionFlowContext]
    workshops: dict[int, Workshop]


@dataclass(slots=True)
class StandardCandidate:
    key: StandardKey
    repositories: list[Repository] = field(default_factory=list)
    activity: PositionActivity = field(default_factory=PositionActivity)


@dataclass(slots=True)
class AssemblyCandidate:
    key: AssemblyKey
    production_item_ids: set[int] = field(default_factory=set)
    repositories: list[Repository] = field(default_factory=list)
    allocations: list[AssemblyInputAllocation] = field(default_factory=list)
    activity: PositionActivity = field(default_factory=PositionActivity)


@dataclass(frozen=True, slots=True)
class CandidateView:
    candidate: StandardCandidate | AssemblyCandidate
    position_type: str
    position_key: str
    representative_item_id: int
    customer_order_item_id: int
    node: dict
    workshop: Workshop
    available_quantity: int


@dataclass(frozen=True, slots=True)
class AssemblyAvailability:
    capacity_quantity: int
    initial_capacity_quantity: int
    continuation_capacity_quantity: int
    input_materials_complete: bool
    required_material_keys: frozenset[str]


def list_production_workbench_positions(
    department_code: str,
    page: int,
    page_size: int,
    customer_order_item_id: int,
    workshop_id: int,
    flow_node_id: str,
    production_item_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        if department_code == "qc":
            return [], 0

        repositories = _department_repositories(
            session,
            department.id,
            customer_order_item_id=customer_order_item_id,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
        )
        activity = load_workbench_activity(
            session,
            department.id,
            department_code,
            customer_order_item_id=customer_order_item_id,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
        )
        item_ids = {repository.production_item_id for repository in repositories}
        item_ids.update(
            item_id
            for item in activity.standard.values()
            for item_id in item.production_item_ids
        )
        item_ids.update(
            item_id
            for item in activity.assembly.values()
            for item_id in item.production_item_ids
        )
        item_ids.update(
            allocation.production_item_id
            for allocation in activity.assembly_allocations
        )
        display = _load_display_data(
            session,
            item_ids,
            expand_order_items=production_item_id is None,
        )
        standard, assembly = _group_candidates(
            repositories,
            activity.standard,
            activity.assembly,
            activity.assembly_allocations,
            display,
        )
        reservation_by_id = reserved_quantities(
            session,
            [repository.id for repository in repositories],
        )
        candidates = _candidate_views(
            standard,
            assembly,
            display,
            department,
            reservation_by_id,
        )
        candidates = _filter_candidates(
            candidates,
            workshop_id,
            customer_order_item_id,
            production_item_id,
            flow_node_id,
        )
        candidates.sort(key=_candidate_sort_key, reverse=True)
        total = len(candidates)
        selected = candidates[(page - 1) * page_size:page * page_size]
        return _serialize_page(
            session,
            selected,
            display,
            department,
            reservation_by_id,
        ), total


def _department_repositories(
    session,
    department_id: int,
    *,
    customer_order_item_id: int | None,
    production_item_id: int | None,
    flow_node_id: str | None,
) -> list[Repository]:
    statement = (
        select(Repository)
        .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionItem.customer_order_item_id,
        )
        .join(
            ProductionPlan,
            ProductionPlan.customer_order_id == CustomerOrderItem.customer_order_id,
        )
        .where(
            Repository.department_id == department_id,
            ProductionPlan.status.in_(("confirmed", "completed")),
        )
        .order_by(Repository.id)
    )
    if customer_order_item_id is not None:
        statement = statement.where(
            ProductionItem.customer_order_item_id == customer_order_item_id
        )
    if production_item_id is not None:
        statement = statement.where(
            Repository.production_item_id == production_item_id
        )
    if flow_node_id is not None:
        statement = statement.where(Repository.flow_node_id == flow_node_id)
    return list(session.scalars(statement))


def _load_display_data(
    session,
    item_ids: set[int],
    *,
    expand_order_items: bool,
) -> DisplayData:
    if not item_ids:
        return DisplayData({}, {}, {}, {}, {}, {})
    seed_items = list(session.scalars(
        select(ProductionItem).where(ProductionItem.id.in_(item_ids))
    ))
    order_item_ids = {item.customer_order_item_id for item in seed_items}
    items = seed_items
    if expand_order_items:
        items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id.in_(order_item_ids)
            )
        ))
    order_items = list(session.scalars(
        select(CustomerOrderItem).where(CustomerOrderItem.id.in_(order_item_ids))
    ))
    order_ids = {item.customer_order_id for item in order_items}
    orders = list(session.scalars(
        select(CustomerOrder).where(CustomerOrder.id.in_(order_ids))
    ))
    customers = list(session.scalars(
        select(Customer).where(Customer.id.in_({order.customer_id for order in orders}))
    ))
    product_ids = {item.product_id for item in items}
    products = list(session.scalars(
        select(Product).where(Product.id.in_(product_ids))
    ))
    bom_ids = {item.product_bom_id for item in items if item.product_bom_id is not None}
    boms = list(session.scalars(
        select(ProductBom).where(ProductBom.id.in_(bom_ids))
    )) if bom_ids else []
    version_keys = {(item.product_id, item.product_version) for item in items}
    flows = list(session.scalars(
        select(ProductProcessFlow).where(
            tuple_(
                ProductProcessFlow.product_id,
                ProductProcessFlow.product_version,
            ).in_(version_keys)
        )
    ))
    presentation = ProductionItemDisplayContext(
        production_items={item.id: item for item in items},
        order_items={item.id: item for item in order_items},
        bom_items={item.id: item for item in boms},
        flow_cache={(item.product_id, item.product_version): item for item in flows},
    )
    contexts = {
        item.id: load_production_flow(
            session,
            item,
            flow_cache=presentation.flow_cache,
            order_items=presentation.order_items,
            bom_items=presentation.bom_items,
        )
        for item in items
    }
    workshop_ids = {
        workshop_id
        for context in contexts.values()
        for node in context.nodes.values()
        if isinstance((workshop_id := node.get("workshop_id")), int)
    }
    workshops = list(session.scalars(
        select(Workshop).where(Workshop.id.in_(workshop_ids))
    )) if workshop_ids else []
    return DisplayData(
        items={item.id: item for item in items},
        orders={item.id: item for item in orders},
        customers={item.id: item for item in customers},
        products={item.id: item for item in products},
        contexts=contexts,
        workshops={item.id: item for item in workshops},
    )


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


def _arrival_times(
    session,
    selected: list[CandidateView],
    display: DisplayData,
    department_id: int,
) -> dict[tuple, datetime]:
    selected_standard = {
        view.candidate.key
        for view in selected
        if isinstance(view.candidate, StandardCandidate)
    }
    selected_assembly = {
        view.candidate.key
        for view in selected
        if isinstance(view.candidate, AssemblyCandidate)
    }
    item_ids = {
        repository.production_item_id
        for view in selected
        for repository in view.candidate.repositories
    }
    item_ids.update(
        item_id
        for view in selected
        for item_id in view.candidate.activity.production_item_ids
    )
    item_ids.update(
        allocation.production_item_id
        for view in selected
        if isinstance(view.candidate, AssemblyCandidate)
        for allocation in view.candidate.allocations
    )
    if not item_ids:
        return {}
    result: dict[tuple, datetime] = {}
    rows = session.execute(
        select(ProductionMovement, WorkOrderBatch.source_flow_node_id)
        .outerjoin(
            WorkOrderBatch,
            WorkOrderBatch.id == ProductionMovement.work_order_batch_id,
        )
        .where(
            ProductionMovement.target_department_id == department_id,
            ProductionMovement.production_item_id.in_(item_ids),
        )
    )
    for movement, batch_source_flow_node_id in rows:
        target_node_id = movement.target_flow_node_id
        if target_node_id is None:
            continue
        source_node_id = (
            batch_source_flow_node_id
            if movement.movement_type == "qc_rework"
            and batch_source_flow_node_id is not None
            else movement.source_flow_node_id
        )
        standard_key = (
            movement.production_item_id,
            target_node_id,
            source_node_id,
        )
        if source_node_id is not None and standard_key in selected_standard:
            _keep_latest(result, ("standard", *standard_key), movement.created_at)
        item = display.items.get(movement.production_item_id)
        if item is not None:
            assembly_key = (item.customer_order_item_id, target_node_id)
            if assembly_key in selected_assembly:
                _keep_latest(result, ("assembly", *assembly_key), movement.created_at)
    return result


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


def _keep_latest(result: dict, key: tuple, timestamp: datetime) -> None:
    if key not in result or result[key] < timestamp:
        result[key] = timestamp


__all__ = ["list_production_workbench_positions"]
