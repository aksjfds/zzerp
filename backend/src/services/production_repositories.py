from sqlalchemy import select

from models.engineering import ProductBom
from models.organization import Procedure, Workshop
from models.production import ProductionItem, Repository
from models.sales import CustomerOrder
from services.errors import DomainError
from services.production_flow import load_product_flow
from services.production_movements import record_movement


def provision_order_repositories(session, order: CustomerOrder) -> None:
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
        normal_edges = [
            edge for edge in flow.get("edges", [])
            if edge.get("route_type", "normal") == "normal"
        ]
        for node in nodes.values():
            if node.get("type") != "process":
                continue
            procedure = session.get(Procedure, node.get("procedure_id"))
            workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
            if workshop is None:
                raise DomainError(
                    "process_procedure_invalid",
                    f"工艺节点“{node.get('label', '')}”未关联有效工艺和车间",
                    path="process_flow",
                )
        part_nodes = {
            node.get("bom_item_id"): node
            for node in nodes.values()
            if node.get("type") == "part"
        }
        for bom_item in bom_items:
            part_node = part_nodes.get(bom_item.id)
            if part_node is None:
                _invalid_first_process(bom_item.part_name, "没有对应配件节点")
            targets = [
                nodes.get(edge.get("target_node_id"))
                for edge in normal_edges
                if edge.get("source_node_id") == part_node["id"]
            ]
            if len(targets) != 1 or targets[0] is None or targets[0].get("type") != "process":
                _invalid_first_process(bom_item.part_name, "必须直接连接且只连接一道首工艺")
            process_node = targets[0]
            procedure = session.get(Procedure, process_node.get("procedure_id"))
            if procedure is None:
                _invalid_first_process(bom_item.part_name, "首工艺未关联有效工艺")
            workshop = session.get(Workshop, procedure.workshop_id)
            if workshop is None:
                _invalid_first_process(bom_item.part_name, "首工艺没有有效车间")
            production_item = ProductionItem(
                customer_order_item_id=order_item.id,
                product_id=order_item.product_id,
                product_version=order_item.product_version,
                product_bom_id=bom_item.id,
                origin_flow_node_id=part_node["id"],
            )
            session.add(production_item)
            session.flush()
            quantity = order_item.quantity * bom_item.pcs
            session.add(Repository(
                production_item_id=production_item.id,
                flow_node_id=process_node["id"],
                source_flow_node_id=part_node["id"],
                department_id=workshop.department_id,
                quantity=quantity,
            ))
            record_movement(
                session,
                production_item=production_item,
                quantity=quantity,
                movement_type="initial",
                source_flow_node_id=part_node["id"],
                target_flow_node_id=process_node["id"],
                target_department_id=workshop.department_id,
            )


def _invalid_first_process(part_name: str, reason: str) -> None:
    raise DomainError(
        "first_process_invalid",
        f"配件“{part_name}”{reason}",
        path="process_flow",
    )
