"""Plan-owned product values and route queries; never read live engineering rows."""

from dataclasses import asdict

from domain.handoff_routes import resolve_handoff_routes
from domain.process_flow import material_routes
from domain.route_order import department_route_order
from schemas.engineering import ProcessFlowPayload
from sqlalchemy import select, tuple_

from modules.engineering.product_reference_api import capture_product_snapshot
from modules.errors import DomainError
from modules.planning.persistence import (
    DepartmentWorkOrder,
    PlanProductRoute,
    ProductionPlanItem,
)
from modules.sales.customer_api import resolve_customer

SNAPSHOT_FIELDS = (
    "source_version", "source_version_value", "product_name", "factory_code", "customer_code", "bom_snapshot", "process_flow_snapshot",
)


def prepare_snapshots(session, payload, plan=None):
    resolve_customer(session, payload.customer_id, None, allow_create=False)
    existing = {}
    if plan is not None and plan.customer_id == payload.customer_id:
        existing = {item.product_id: item for item in session.scalars(select(ProductionPlanItem).where(
            ProductionPlanItem.production_plan_id == plan.id))}
    result = {}
    for item in sorted(payload.items, key=lambda item: item.product_id):
        previous = existing.get(item.product_id)
        if previous is not None and (item.source_version is None or item.source_version == previous.source_version):
            result[item.product_id] = {key: getattr(previous, key) for key in SNAPSHOT_FIELDS}
        else:
            snapshot = capture_product_snapshot(session, item.product_id, payload.customer_id, item.source_version)
            result[item.product_id] = asdict(snapshot)
            result[item.product_id].pop("product_id")
            result[item.product_id]["bom_snapshot"] = [asdict(part) for part in snapshot.bom_snapshot]
    return result


def create_snapshot_routes(session, item):
    flow = ProcessFlowPayload.model_validate(item.process_flow_snapshot)
    parts = {part["id"]: part for part in item.bom_snapshot}
    nodes = {node.id: node for node in flow.nodes}
    routes = material_routes(flow)
    if not routes:
        raise DomainError("plan_snapshot_routes_missing", "产品外观版本缺少完整正式路线，不能创建计划")
    for route in routes:
        members = sorted((parts[nodes[key].bom_item_id] for key in route.part_node_ids), key=lambda part: part["part_no"])
        assembly = len(members) > 1
        session.add(PlanProductRoute(
            production_plan_id=item.production_plan_id, product_id=item.product_id,
            material_node_id=route.material_node_id, department_node_id=route.department_node_id,
            department_code=nodes[route.department_node_id].department_code,
            part_no=" + ".join(part["part_no"] for part in members),
            part_name="（" + "+".join(part["part_name"] for part in members) + "）装配体" if assembly else members[0]["part_name"],
            unit_requirement=1 if assembly else members[0]["pcs"],
        ))


def item_key(order):
    return order.production_plan_id, order.product_id


def route_key(order):
    return *item_key(order), order.material_node_id, order.department_node_id


def snapshot_items(session, keys):
    if not keys:
        return {}
    return {item_key(item): item for item in session.scalars(select(ProductionPlanItem).where(
        tuple_(ProductionPlanItem.production_plan_id, ProductionPlanItem.product_id).in_(keys)))}


def route_references(session, *, item_keys=None, route_keys=None):
    statement = select(PlanProductRoute)
    if item_keys is not None:
        if not item_keys:
            return {}
        statement = statement.where(tuple_(PlanProductRoute.production_plan_id, PlanProductRoute.product_id).in_(item_keys))
    if route_keys is not None:
        if not route_keys:
            return {}
        statement = statement.where(tuple_(PlanProductRoute.production_plan_id, PlanProductRoute.product_id,
            PlanProductRoute.material_node_id, PlanProductRoute.department_node_id).in_(route_keys))
    return {route_key(row): row for row in session.scalars(statement)}


def order_department_filter(code):
    return select(PlanProductRoute.product_id).where(
        PlanProductRoute.production_plan_id == DepartmentWorkOrder.production_plan_id,
        PlanProductRoute.product_id == DepartmentWorkOrder.product_id,
        PlanProductRoute.material_node_id == DepartmentWorkOrder.material_node_id,
        PlanProductRoute.department_node_id == DepartmentWorkOrder.department_node_id,
        PlanProductRoute.department_code == code,
    ).exists()


def order_product_filter(keyword):
    pattern = f"%{keyword.strip()}%"
    return select(ProductionPlanItem.product_id).where(
        ProductionPlanItem.production_plan_id == DepartmentWorkOrder.production_plan_id,
        ProductionPlanItem.product_id == DepartmentWorkOrder.product_id,
        ProductionPlanItem.factory_code.ilike(pattern) | ProductionPlanItem.product_name.ilike(pattern),
    ).exists()


def snapshot_context(item):
    flow = ProcessFlowPayload.model_validate(item.process_flow_snapshot)
    bom = {part["id"]: part for part in item.bom_snapshot}
    parts = {node.id: bom[node.bom_item_id] for node in flow.nodes if node.type == "part"}
    materials = {key: part["part_name"] for key, part in parts.items()}
    receipt_materials = {key: {key} for key in parts}
    requirements = {key: {key: 1} for key in parts}
    for route in material_routes(flow):
        receipt_materials[route.material_node_id] = {route.material_node_id, *route.part_node_ids}
        if route.material_node_id not in parts:
            requirements[route.material_node_id] = {key: parts[key]["pcs"] for key in route.part_node_ids}
        if route.material_node_id not in materials:
            members = sorted((parts[key] for key in route.part_node_ids), key=lambda part: part["part_no"])
            materials[route.material_node_id] = "（" + "+".join(part["part_name"] for part in members) + "）装配体"
    return {
        "routes": resolve_handoff_routes(flow), "materials": materials,
        "receipt_materials": receipt_materials, "requirements": requirements,
        "parts": {key: {"part_no": part["part_no"], "part_name": part["part_name"]} for key, part in parts.items()},
    }


def material_number(context, material_node_id: str) -> str:
    parts = context["parts"]
    part_ids = context["requirements"][material_node_id]
    return " + ".join(parts[part_id]["part_no"] for part_id in sorted(part_ids, key=lambda key: parts[key]["part_no"]))


def handoff_contexts(session, keys):
    return {key: snapshot_context(item) for key, item in snapshot_items(session, keys).items()}


def snapshot_department_orders(session, keys):
    return {key: department_route_order(ProcessFlowPayload.model_validate(item.process_flow_snapshot))
            for key, item in snapshot_items(session, keys).items()}
