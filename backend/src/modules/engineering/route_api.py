"""Live material routes derived from the current formal graph, without snapshots."""

from dataclasses import dataclass
from sqlalchemy import select, tuple_

from domain.process_flow import material_routes
from modules.engineering.persistence import (
    Product, ProductBom, ProductDepartmentRoute, ProductProcessFlow, ProductRouteComponent,
)
from modules.engineering.routing import validate_nodes
from modules.errors import DomainError
from schemas.engineering import ProcessFlowPayload


@dataclass(frozen=True, slots=True)
class RouteReference:
    product_id: int
    material_node_id: str
    department_node_id: str
    part_no: str
    part_name: str
    unit_requirement: int
    department_code: str


def current_route_references(session, *, product_ids=None, route_keys=None, department_code=None):
    statement = (
        select(ProductDepartmentRoute.product_id, ProductDepartmentRoute.material_node_id,
               ProductDepartmentRoute.department_node_id, ProductDepartmentRoute.department_code,
               ProductBom.id, ProductBom.part_no, ProductBom.part_name, ProductBom.pcs)
        .join(ProductRouteComponent,
              (ProductRouteComponent.product_id == ProductDepartmentRoute.product_id)
              & (ProductRouteComponent.material_node_id == ProductDepartmentRoute.material_node_id)
              & (ProductRouteComponent.department_node_id == ProductDepartmentRoute.department_node_id))
        .join(ProductBom, ProductBom.id == ProductRouteComponent.product_bom_id)
        .order_by(ProductDepartmentRoute.product_id, ProductDepartmentRoute.material_node_id,
                  ProductDepartmentRoute.department_node_id, ProductBom.part_no)
    )
    if product_ids is not None:
        if not product_ids:
            return {}
        statement = statement.where(ProductDepartmentRoute.product_id.in_(product_ids))
    if route_keys is not None:
        if not route_keys:
            return {}
        statement = statement.where(tuple_(ProductDepartmentRoute.product_id, ProductDepartmentRoute.material_node_id,
                                           ProductDepartmentRoute.department_node_id).in_(route_keys))
    if department_code is not None:
        statement = statement.where(ProductDepartmentRoute.department_code == department_code)
    grouped = {}
    for row in session.execute(statement):
        grouped.setdefault((row[0], row[1], row[2]), []).append(row)
    result = {}
    for key, rows in grouped.items():
        assembly = len(rows) > 1
        result[key] = RouteReference(
            *key, part_no=" + ".join(row[5] for row in rows),
            part_name="（" + "+".join(row[6] for row in rows) + "）装配体" if assembly else rows[0][6],
            unit_requirement=1 if assembly else rows[0][7], department_code=rows[0][3],
        )
    return result


def validated_plan_routes(session, product_id):
    record = session.scalar(
        select(ProductProcessFlow).join(Product, (Product.id == ProductProcessFlow.product_id)
        & (Product.version == ProductProcessFlow.product_version)).where(Product.id == product_id)
    )
    if record is None:
        raise DomainError("production_plan_flow_missing", "产品当前版本缺少正式流程图")
    flow = validate_nodes(session, product_id, record.product_version, ProcessFlowPayload.model_validate(record.flow_json))
    routes = material_routes(flow)
    if not routes:
        raise DomainError("production_plan_routes_missing", "请先连接配件节点和部门节点并保存正式流程")
    nodes = {node.id: node for node in flow.nodes}
    expected = {
        (product_id, route.material_node_id, route.department_node_id):
        (nodes[route.department_node_id].department_code,
         {nodes[part].bom_item_id for part in route.part_node_ids})
        for route in routes
    }
    actual = {}
    for material_id, department_id, code in session.execute(select(
        ProductDepartmentRoute.material_node_id, ProductDepartmentRoute.department_node_id,
        ProductDepartmentRoute.department_code,
    ).where(ProductDepartmentRoute.product_id == product_id)):
        actual[(product_id, material_id, department_id)] = (code, set())
    for material_id, department_id, bom_id in session.execute(select(
        ProductRouteComponent.material_node_id, ProductRouteComponent.department_node_id,
        ProductRouteComponent.product_bom_id,
    ).where(ProductRouteComponent.product_id == product_id)):
        key = (product_id, material_id, department_id)
        if key in actual:
            actual[key][1].add(bom_id)
    if actual != expected:
        raise DomainError("production_route_inconsistent", "当前路线索引与正式流程不一致，请重新保存正式流程", status_code=409)
    return current_route_references(session, product_ids={product_id})
