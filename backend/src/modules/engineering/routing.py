"""Current route projection derived solely from the formal node graph."""

from sqlalchemy import delete, select

from domain.process_flow import material_routes
from modules.engineering.persistence import ProductBom, ProductDepartmentRoute, ProductRouteComponent
from modules.errors import DomainError
from schemas.engineering import ProcessFlowPayload
from modules.organization.read_api import department_names, validate_departments


def validate_nodes(session, product_id, version, flow):
    material_routes(flow)
    bom = {row.id: row for row in session.scalars(select(ProductBom).where(
        ProductBom.product_id == product_id, ProductBom.product_version == version,
    ))}
    for node in flow.nodes:
        if node.type == "part" and node.bom_item_id not in bom:
            raise DomainError("flow_part_bom_invalid", "配件节点必须引用当前版本 BOM", path="process_flow.nodes", element_id=node.id)
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



def route_identities(product, flow):
    nodes = {node.id: node for node in flow.nodes}
    bom = {row.id: row for row in product.bom_items}
    return {
        (route.material_node_id, route.department_node_id):
        (tuple(sorted(bom[nodes[part].bom_item_id].part_no for part in route.part_node_ids)),
         nodes[route.department_node_id].department_code)
        for route in material_routes(flow)
    }


def ensure_recorded_inputs_preserved(product, flow, input_ids):
    if not input_ids:
        return
    payload = next(record.flow_json for record in product.process_flows if record.product_version == product.version)
    current = ProcessFlowPayload.model_validate(payload)
    bom = {item.id: item.part_no for item in product.bom_items}
    def identities(graph):
        return {node.id: (node.type, bom[node.bom_item_id] if node.type == "part" else node.department_code)
                for node in graph.nodes}
    before, after = identities(current), identities(flow)
    if any(key not in before or before[key] != after.get(key) for key in input_ids):
        raise DomainError("recorded_input_in_use", "物料节点已有到料流水，不能删除、换号或更换其身份", status_code=409)


def ensure_referenced_routes_preserved(session, product, flow, referenced_pairs):
    if not referenced_pairs:
        return
    current_flow = next(record.flow_json for record in product.process_flows if record.product_version == product.version)
    current = route_identities(product, ProcessFlowPayload.model_validate(current_flow))
    proposed = route_identities(product, flow)
    for pair in referenced_pairs:
        if pair not in proposed:
            raise DomainError("scheduled_route_in_use", "路线已有部门工单，不能删除物料来源或断开路线", status_code=409)
        if pair not in current or current[pair] != proposed[pair]:
            raise DomainError("scheduled_route_changed", "路线已有部门工单，不能更换组成配件或部门", status_code=409)


def ensure_referenced_bom_identity(session, product, version, commands, referenced_pairs):
    if version != product.version or not referenced_pairs:
        return
    proposed = {command.id: command.part_no for command in commands if command.id is not None}
    for material_id, department_id, bom_id, part_no in session.execute(
        select(ProductRouteComponent.material_node_id, ProductRouteComponent.department_node_id,
               ProductBom.id, ProductBom.part_no)
        .join(ProductBom, ProductBom.id == ProductRouteComponent.product_bom_id)
        .where(ProductRouteComponent.product_id == product.id)
    ):
        if (material_id, department_id) in referenced_pairs and proposed.get(bom_id) != part_no:
            raise DomainError("scheduled_bom_in_use", "配件已有部门工单，不能删除或更换配件编号", status_code=409)
