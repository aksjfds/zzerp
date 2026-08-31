from sqlalchemy import select

from modules.engineering.model_api import ProductBom
from modules.organization.model_api import Workshop
from modules.production_core.persistence import ProductionItem, Repository
from modules.sales.model_api import CustomerOrder
from modules.errors import DomainError
from modules.production_core.flow import load_product_flow
from modules.production_core.movements import record_movement
from modules.production_core.work_order_support import target_department_id


def provision_order_repositories(
    session,
    order: CustomerOrder,
    *,
    part_quantities: dict[tuple[int, int, str], int] | None = None,
) -> None:
    for order_item in order.items:
        bom_items = session.scalars(
            select(ProductBom)
            .where(
                ProductBom.product_id == order_item.product_id,
                ProductBom.product_version == order_item.product_version,
            )
            .order_by(ProductBom.sort_order)
        ).all()
        try:
            flow, nodes = load_product_flow(
                session, order_item.product_id, order_item.product_version
            )
        except DomainError:
            raise DomainError(
                "product_engineering_data_missing",
                "订单产品版本缺少 BOM 或流程图",
                path="items",
            )
        if not bom_items:
            raise DomainError(
                "product_engineering_data_missing",
                "订单产品版本缺少 BOM 或流程图",
                path="items",
            )
        normal_edges = flow.get("edges", [])
        for node in nodes.values():
            if node.get("type") != "process":
                continue
            workshop = session.get(Workshop, node.get("workshop_id"))
            if workshop is None:
                raise DomainError(
                    "process_workshop_invalid",
                    f"流程节点“{node.get('label', '')}”未关联有效车间",
                    path="process_flow",
                )
        part_nodes: dict[int, list[dict]] = {}
        for node in nodes.values():
            if node.get("type") == "part":
                part_nodes.setdefault(node.get("bom_item_id"), []).append(node)
        for bom_item in bom_items:
            part_routes = part_nodes.get(bom_item.id, [])
            if len(part_routes) != 1:
                _invalid_first_node(bom_item.part_name, "必须且只能有一个配件节点")
            part_node = part_routes[0]
            targets = [
                nodes.get(edge.get("target_node_id"))
                for edge in normal_edges
                if edge.get("source_node_id") == part_node["id"]
            ]
            if (
                len(targets) != 1
                or targets[0] is None
                or targets[0].get("type") not in {
                    "process",
                    "assembly",
                    "supplier_processing",
                }
            ):
                _invalid_first_node(
                    bom_item.part_name,
                    "必须直接连接且只连接一个工艺、装配或委外加工节点",
                )
            first_node = targets[0]
            quantity = (
                part_quantities.get((order_item.id, bom_item.id, part_node["id"]), 0)
                if part_quantities is not None
                else order_item.quantity * bom_item.pcs
            )
            if quantity <= 0:
                continue
            production_item = ProductionItem(
                customer_order_item_id=order_item.id,
                product_id=order_item.product_id,
                product_version=order_item.product_version,
                product_bom_id=bom_item.id,
                origin_flow_node_id=part_node["id"],
            )
            session.add(production_item)
            session.flush()
            if first_node.get("type") == "supplier_processing":
                continue
            try:
                department_id = target_department_id(session, first_node)
            except DomainError:
                _invalid_first_node(bom_item.part_name, "首节点没有有效生产部门")
            session.add(Repository(
                production_item_id=production_item.id,
                flow_node_id=first_node["id"],
                source_flow_node_id=part_node["id"],
                department_id=department_id,
                quantity=quantity,
            ))
            record_movement(
                session,
                production_item=production_item,
                quantity=quantity,
                movement_type="initial",
                source_flow_node_id=part_node["id"],
                target_flow_node_id=first_node["id"],
                target_department_id=department_id,
            )


def _invalid_first_node(part_name: str, reason: str) -> None:
    raise DomainError(
        "first_flow_node_invalid",
        f"配件“{part_name}”{reason}",
        path="process_flow",
    )
