"""Current route projection derived solely from the formal node graph."""

from domain.process_flow import material_routes
from sqlalchemy import delete, select

from modules.engineering.persistence import (
    ProductBom,
    ProductDepartmentRoute,
    ProductRouteComponent,
)
from modules.errors import DomainError
from modules.organization.read_api import department_names, validate_departments


def validate_nodes(session, product_id, version, flow):
    material_routes(flow)
    bom = {row.id: row for row in session.scalars(select(ProductBom).where(
        ProductBom.product_id == product_id, ProductBom.product_version == version,
    ))}
    for node in flow.nodes:
        if node.type == "part" and node.bom_item_id not in bom:
            raise DomainError("flow_part_bom_invalid", "配件节点必须引用当前外观版本 BOM", path="process_flow.nodes", element_id=node.id)
    codes = {node.department_code for node in flow.nodes if node.type == "department"}
    validate_departments(session, codes)
    names = department_names(session, codes)
    result = flow.model_copy(deep=True)
    for node in result.nodes:
        if node.type == "part":
            row = bom[node.bom_item_id]
            node.label = f"{row.part_no} · {row.part_name}"
        else:
            node.label = names[node.department_code]
    return result



def synchronize_routes(session, product_id, flow):
    nodes = {node.id: node for node in flow.nodes}
    routes = material_routes(flow)
    proposed = {(route.material_node_id, route.department_node_id): route for route in routes}
    existing = {
        (row.material_node_id, row.department_node_id): row
        for row in session.scalars(select(ProductDepartmentRoute).where(ProductDepartmentRoute.product_id == product_id))
    }
    session.execute(delete(ProductRouteComponent).where(ProductRouteComponent.product_id == product_id))
    session.flush()
    for key, row in existing.items():
        if key not in proposed:
            session.delete(row)
    for key, route in proposed.items():
        row = existing.get(key)
        if row is None:
            row = ProductDepartmentRoute(product_id=product_id, material_node_id=key[0], department_node_id=key[1])
            session.add(row)
        row.department_code = nodes[route.department_node_id].department_code
    session.flush()
    for route in routes:
        for part in route.part_node_ids:
            session.add(ProductRouteComponent(
                product_id=product_id, material_node_id=route.material_node_id,
                department_node_id=route.department_node_id, product_bom_id=nodes[part].bom_item_id,
            ))
    session.flush()

def ensure_bom_nodes_retained(product, version, retained_ids):
    referenced = set()
    for record in product.process_flows:
        if record.product_version != version:
            continue
        for payload in [record.flow_json, record.draft_flow_json]:
            if payload:
                referenced.update(node["bom_item_id"] for node in payload["nodes"] if node["type"] == "part")
    if referenced - retained_ids:
        raise DomainError("flow_part_in_use", "配件已被正式或草稿节点引用，请先调整流程图", status_code=409)
