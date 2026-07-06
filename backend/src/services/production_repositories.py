from sqlalchemy import select

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow
from models.organization import Department, Procedure, Workshop
from models.production import Repository
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError


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
        process_flow = session.scalar(
            select(ProductProcessFlow).where(
                ProductProcessFlow.product_id == order_item.product_id,
                ProductProcessFlow.product_version == order_item.product_version,
            )
        )
        if not bom_items or process_flow is None:
            raise DomainError(
                "product_engineering_data_missing",
                "订单产品版本缺少 BOM 或流程图",
                path="items",
            )
        nodes = {node["id"]: node for node in process_flow.flow_json.get("nodes", [])}
        normal_edges = [
            edge
            for edge in process_flow.flow_json.get("edges", [])
            if edge.get("route_type", "normal") == "normal"
        ]
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
            procedure_id = process_node.get("procedure_id")
            procedure = session.get(Procedure, procedure_id) if procedure_id else None
            if procedure is None:
                _invalid_first_process(bom_item.part_name, "首工艺未关联有效工艺")
            workshop = session.get(Workshop, procedure.workshop_id)
            if workshop is None:
                _invalid_first_process(bom_item.part_name, "首工艺没有有效车间")
            session.add(
                Repository(
                    customer_order_item_id=order_item.id,
                    product_bom_id=bom_item.id,
                    flow_node_id=process_node["id"],
                    department_id=workshop.department_id,
                    quantity=order_item.quantity * bom_item.pcs,
                )
            )


def _invalid_first_process(part_name: str, reason: str) -> None:
    raise DomainError(
        "first_process_invalid",
        f"配件“{part_name}”{reason}",
        path="process_flow",
    )


def list_department_repositories(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        rows = session.scalars(
            select(Repository)
            .where(Repository.department_id == department.id)
            .order_by(Repository.id.desc())
        ).all()
        return [_serialize_repository(session, row, department) for row in rows]


def _serialize_repository(session, row: Repository, department: Department) -> dict:
    order_item = session.get(CustomerOrderItem, row.customer_order_item_id)
    order = session.get(CustomerOrder, order_item.customer_order_id)
    product = session.get(Product, order_item.product_id)
    bom_item = session.get(ProductBom, row.product_bom_id)
    flow = session.scalar(
        select(ProductProcessFlow).where(
            ProductProcessFlow.product_id == order_item.product_id,
            ProductProcessFlow.product_version == order_item.product_version,
        )
    )
    node = next(
        (
            item
            for item in flow.flow_json.get("nodes", [])
            if item.get("id") == row.flow_node_id
        ),
        {},
    )
    procedure_id = node.get("procedure_id")
    procedure = session.get(Procedure, procedure_id) if procedure_id else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    return {
        "id": row.id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": bom_item.id,
        "part_name": bom_item.part_name,
        "part_no": bom_item.part_no,
        "flow_node_id": row.flow_node_id,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": row.quantity,
        "delivery_date": order_item.delivery_date,
    }
