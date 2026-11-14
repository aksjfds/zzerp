"""Live material routes derived from the current formal graph, without snapshots."""

from collections.abc import Collection

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import (
    HandoffContext,
    MaterialPart,
    ProcessFlowPayload,
    RouteReference,
)
from zzerp.modules.engineering.flow import material_routes
from zzerp.modules.engineering.handoff_routes import resolve_handoff_routes
from zzerp.modules.engineering.persistence import (
    ProductAppearance,
    ProductBom,
    ProductDepartmentRoute,
    ProductProcessFlow,
    ProductRouteComponent,
)
from zzerp.modules.engineering.route_order import department_route_order
from zzerp.modules.engineering.routing import validate_nodes


def department_route_keys_query(department_code: str) -> Select[tuple[int, int, str, str]]:
    """Scalar projection for database-side scoping; callers never receive our ORM."""
    return select(
        ProductDepartmentRoute.product_id,
        ProductDepartmentRoute.appearance_id,
        ProductDepartmentRoute.material_node_id,
        ProductDepartmentRoute.department_node_id,
    ).where(ProductDepartmentRoute.department_code == department_code)


def route_department_code(
    session: Session,
    product_id: int,
    appearance_id: int,
    material_node_id: str,
    department_node_id: str,
) -> str | None:
    return session.scalar(
        select(ProductDepartmentRoute.department_code).where(
            ProductDepartmentRoute.product_id == product_id,
            ProductDepartmentRoute.appearance_id == appearance_id,
            ProductDepartmentRoute.material_node_id == material_node_id,
            ProductDepartmentRoute.department_node_id == department_node_id,
        )
    )


def handoff_contexts(session: Session, appearance_ids: set[int]) -> dict[int, HandoffContext]:
    if not appearance_ids:
        return {}
    records = list(
        session.execute(
            select(
                ProductProcessFlow.appearance_id,
                ProductProcessFlow.product_id,
                ProductProcessFlow.flow_json,
            )
            .join(ProductAppearance, ProductAppearance.id == ProductProcessFlow.appearance_id)
            .where(ProductAppearance.id.in_(appearance_ids))
        )
    )
    if {row[0] for row in records} != appearance_ids:
        raise DomainError("handoff_flow_missing", "产品缺少当前正式流程图", status_code=409)
    bom = {
        row.id: row
        for row in session.scalars(
            select(ProductBom).where(ProductBom.product_id.in_({pid for aid, pid, flow in records}))
        )
    }
    result = {}
    for appearance_id, product_id, payload in records:
        flow = ProcessFlowPayload.model_validate(payload)
        parts = {}
        for node in flow.nodes:
            if node.type == "part":
                item = bom.get(node.bom_item_id)
                if item is None or item.product_id != product_id:
                    raise DomainError("handoff_part_missing", "流程配件不存在", status_code=409)
                parts[node.id] = item
        materials = {key: row.part_name for key, row in parts.items()}
        receipt_materials = {key: frozenset({key}) for key in parts}
        requirements = {key: {key: 1} for key in parts}
        for route in material_routes(flow):
            receipt_materials[route.material_node_id] = frozenset(
                {route.material_node_id, *route.part_node_ids}
            )
            if route.material_node_id not in parts:
                requirements[route.material_node_id] = {
                    part: parts[part].pcs for part in route.part_node_ids
                }
            if route.material_node_id not in materials:
                members = sorted(
                    (parts[key] for key in route.part_node_ids), key=lambda row: row.part_no
                )
                materials[route.material_node_id] = (
                    "（" + "+".join(row.part_name for row in members) + "）装配体"
                )
        result[appearance_id] = HandoffContext(
            routes=resolve_handoff_routes(flow),
            material_names=materials,
            receipt_materials=receipt_materials,
            requirements=requirements,
            parts={
                key: MaterialPart(part_no=part.part_no, part_name=part.part_name)
                for key, part in parts.items()
            },
        )
    return result


def current_department_orders(
    session: Session, appearance_ids: set[int]
) -> dict[int, dict[str, int]]:
    if not appearance_ids:
        return {}
    rows = list(
        session.execute(
            select(ProductProcessFlow.appearance_id, ProductProcessFlow.flow_json)
            .join(ProductAppearance, ProductAppearance.id == ProductProcessFlow.appearance_id)
            .where(ProductAppearance.id.in_(appearance_ids))
        )
    )
    if {appearance_id for appearance_id, payload in rows} != appearance_ids:
        raise DomainError("progress_flow_missing", "外观缺少正式流程图", status_code=409)
    return {
        appearance_id: department_route_order(ProcessFlowPayload.model_validate(payload))
        for appearance_id, payload in rows
    }


def current_route_references(
    session: Session,
    *,
    product_ids: Collection[int] | None = None,
    route_keys: Collection[tuple[int, int, str, str]] | None = None,
    department_code: str | None = None,
) -> dict[tuple[int, int, str, str], RouteReference]:
    statement = (
        select(
            ProductDepartmentRoute.product_id,
            ProductDepartmentRoute.appearance_id,
            ProductDepartmentRoute.material_node_id,
            ProductDepartmentRoute.department_node_id,
            ProductDepartmentRoute.department_code,
            ProductBom.id,
            ProductBom.part_no,
            ProductBom.part_name,
            ProductBom.pcs,
        )
        .join(
            ProductRouteComponent,
            (ProductRouteComponent.product_id == ProductDepartmentRoute.product_id)
            & (ProductRouteComponent.appearance_id == ProductDepartmentRoute.appearance_id)
            & (ProductRouteComponent.material_node_id == ProductDepartmentRoute.material_node_id)
            & (
                ProductRouteComponent.department_node_id
                == ProductDepartmentRoute.department_node_id
            ),
        )
        .join(ProductBom, ProductBom.id == ProductRouteComponent.product_bom_id)
        .order_by(
            ProductDepartmentRoute.product_id,
            ProductDepartmentRoute.appearance_id,
            ProductDepartmentRoute.material_node_id,
            ProductDepartmentRoute.department_node_id,
            ProductBom.part_no,
        )
    )
    if product_ids is not None:
        if not product_ids:
            return {}
        statement = statement.where(ProductDepartmentRoute.product_id.in_(product_ids))
    if route_keys is not None:
        if not route_keys:
            return {}
        statement = statement.where(
            tuple_(
                ProductDepartmentRoute.product_id,
                ProductDepartmentRoute.appearance_id,
                ProductDepartmentRoute.material_node_id,
                ProductDepartmentRoute.department_node_id,
            ).in_(route_keys)
        )
    if department_code is not None:
        statement = statement.where(ProductDepartmentRoute.department_code == department_code)
    grouped = {}
    for row in session.execute(statement):
        grouped.setdefault((row[0], row[1], row[2], row[3]), []).append(row)
    result = {}
    for key, rows in grouped.items():
        assembly = len(rows) > 1
        result[key] = RouteReference(
            *key,
            part_no=" + ".join(row[6] for row in rows),
            part_name="（" + "+".join(row[7] for row in rows) + "）装配体"
            if assembly
            else rows[0][7],
            unit_requirement=1 if assembly else rows[0][8],
            department_code=rows[0][4],
        )
    return result


def validated_plan_routes(
    session: Session, product_id: int, appearance_id: int
) -> dict[tuple[int, int, str, str], RouteReference]:
    record = session.scalar(
        select(ProductProcessFlow)
        .join(ProductAppearance, ProductAppearance.id == ProductProcessFlow.appearance_id)
        .where(
            ProductProcessFlow.product_id == product_id,
            ProductProcessFlow.appearance_id == appearance_id,
        )
    )
    if record is None:
        raise DomainError("production_plan_flow_missing", "所选产品外观缺少正式流程图")
    flow = validate_nodes(
        session,
        product_id,
        ProcessFlowPayload.model_validate(record.flow_json),
    )
    routes = material_routes(flow)
    if not routes:
        raise DomainError(
            "production_plan_routes_missing", "请先连接配件节点和部门节点并保存正式流程"
        )
    nodes = {node.id: node for node in flow.nodes}
    expected = {
        (product_id, appearance_id, route.material_node_id, route.department_node_id): (
            nodes[route.department_node_id].department_code,
            {nodes[part].bom_item_id for part in route.part_node_ids},
        )
        for route in routes
    }
    actual = {}
    for material_id, department_id, code in session.execute(
        select(
            ProductDepartmentRoute.material_node_id,
            ProductDepartmentRoute.department_node_id,
            ProductDepartmentRoute.department_code,
        ).where(
            ProductDepartmentRoute.product_id == product_id,
            ProductDepartmentRoute.appearance_id == appearance_id,
        )
    ):
        actual[(product_id, appearance_id, material_id, department_id)] = (code, set())
    for material_id, department_id, bom_id in session.execute(
        select(
            ProductRouteComponent.material_node_id,
            ProductRouteComponent.department_node_id,
            ProductRouteComponent.product_bom_id,
        ).where(
            ProductRouteComponent.product_id == product_id,
            ProductRouteComponent.appearance_id == appearance_id,
        )
    ):
        key = (product_id, appearance_id, material_id, department_id)
        if key in actual:
            actual[key][1].add(bom_id)
    if actual != expected:
        raise DomainError(
            "production_route_inconsistent",
            "当前路线索引与正式流程不一致，请重新保存正式流程",
            status_code=409,
        )
    return {
        key: value
        for key, value in current_route_references(session, product_ids={product_id}).items()
        if key[1] == appearance_id
    }
