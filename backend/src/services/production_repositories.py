from sqlalchemy import select

from models.engineering import ProductBom
from models.organization import Procedure, Workshop
from models.production import ProductionItem, Repository
from models.sales import CustomerOrder
from services.errors import DomainError
from services.production_flow import load_product_flow
from services.production_movements import record_movement
from services.work_order_support import target_department_id


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
        normal_edges = flow.get("edges", [])
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
                _invalid_first_node(bom_item.part_name, "没有对应配件节点")
            targets = [
                nodes.get(edge.get("target_node_id"))
                for edge in normal_edges
                if edge.get("source_node_id") == part_node["id"]
            ]
            if (
                len(targets) != 1
                or targets[0] is None
                or targets[0].get("type") not in {"process", "assembly"}
            ):
                _invalid_first_node(bom_item.part_name, "必须直接连接且只连接一个工艺或装配节点")
            first_node = targets[0]
            try:
                department_id = target_department_id(session, first_node)
            except DomainError:
                _invalid_first_node(bom_item.part_name, "首节点没有有效生产部门")
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
