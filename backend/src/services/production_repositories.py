from sqlalchemy import func, select

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow
from models.organization import Department, Procedure, Workshop
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderMaterial
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
            procedure_id = process_node.get("procedure_id")
            procedure = session.get(Procedure, procedure_id) if procedure_id else None
            if procedure is None:
                _invalid_first_process(bom_item.part_name, "首工艺未关联有效工艺")
            workshop = session.get(Workshop, procedure.workshop_id)
            if workshop is None:
                _invalid_first_process(bom_item.part_name, "首工艺没有有效车间")
            production_item = ProductionItem(
                customer_order_item_id=order_item.id,
                product_bom_id=bom_item.id,
                origin_flow_node_id=part_node["id"],
            )
            session.add(production_item)
            session.flush()
            session.add(
                Repository(
                    production_item_id=production_item.id,
                    flow_node_id=process_node["id"],
                    source_flow_node_id=part_node["id"],
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


def list_department_repositories(
    department_code: str, page: int, page_size: int
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        base = (
            select(
                Repository,
                ProductionItem,
                CustomerOrderItem,
                CustomerOrder,
                Product,
                ProductBom,
            )
            .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
            .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .join(Product, Product.id == CustomerOrderItem.product_id)
            .outerjoin(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
            .where(Repository.department_id == department.id)
        )
        total = session.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        rows = session.execute(
            base.order_by(Repository.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        repository_ids = [row.Repository.id for row in rows]
        reserved_by_id: dict[int, int] = {}
        if repository_ids:
            for repository_id, reserved in session.execute(
                select(
                    WorkOrder.repository_id,
                    func.sum(WorkOrder.quantity - WorkOrder.completed_quantity),
                )
                .where(
                    WorkOrder.repository_id.in_(repository_ids),
                    WorkOrder.status == "open",
                )
                .group_by(WorkOrder.repository_id)
            ):
                reserved_by_id[repository_id] = reserved
            for repository_id, reserved in session.execute(
                select(
                    WorkOrderMaterial.repository_id,
                    func.sum(WorkOrderMaterial.quantity),
                )
                .join(WorkOrder, WorkOrder.id == WorkOrderMaterial.work_order_id)
                .where(
                    WorkOrderMaterial.repository_id.in_(repository_ids),
                    WorkOrder.status == "open",
                )
                .group_by(WorkOrderMaterial.repository_id)
            ):
                reserved_by_id[repository_id] = reserved_by_id.get(repository_id, 0) + reserved
        data = [
            _serialize_repository(
                session,
                row.Repository,
                row.ProductionItem,
                row.CustomerOrderItem,
                row.CustomerOrder,
                row.Product,
                row.ProductBom,
                department,
                reserved_by_id.get(row.Repository.id, 0),
            )
            for row in rows
        ]
        return data, total


def _serialize_repository(
    session,
    row: Repository,
    production_item: ProductionItem,
    order_item: CustomerOrderItem,
    order: CustomerOrder,
    product: Product,
    bom_item: ProductBom | None,
    department: Department,
    reserved: int,
) -> dict:
    flow_cache = session.info.setdefault("product_process_flow_cache", {})
    flow_key = (order_item.product_id, order_item.product_version)
    if flow_key not in flow_cache:
        flow_cache[flow_key] = session.scalar(
            select(ProductProcessFlow).where(
                ProductProcessFlow.product_id == order_item.product_id,
                ProductProcessFlow.product_version == order_item.product_version,
            )
        )
    flow = flow_cache[flow_key]
    node = next(
        (
            item
            for item in flow.flow_json.get("nodes", [])
            if item.get("id") == row.flow_node_id
        ),
        {},
    )
    source_node = next(
        (
            item
            for item in flow.flow_json.get("nodes", [])
            if item.get("id") == row.source_flow_node_id
        ),
        {},
    )
    procedure_id = node.get("procedure_id")
    procedure = session.get(Procedure, procedure_id) if procedure_id else None
    workshop = session.get(Workshop, procedure.workshop_id) if procedure else None
    origin_node = next(
        (
            item
            for item in flow.flow_json.get("nodes", [])
            if item.get("id") == production_item.origin_flow_node_id
        ),
        {},
    )
    item_name = (
        bom_item.part_name
        if bom_item
        else origin_node.get("output_name") or origin_node.get("label") or "装配体"
    )
    item_no = bom_item.part_no if bom_item else item_name
    return {
        "id": row.id,
        "production_item_id": production_item.id,
        "customer_order_item_id": order_item.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "product_id": product.id,
        "product_version": order_item.product_version,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_bom_id": bom_item.id if bom_item else None,
        "part_name": item_name,
        "part_no": item_no,
        "flow_node_id": row.flow_node_id,
        "source_flow_node_id": row.source_flow_node_id,
        "source_node_label": source_node.get("label", "未知来源"),
        "procedure_name": procedure.procedure_name if procedure else node.get("label", ""),
        "workshop_name": workshop.workshop_name if workshop else "",
        "department_id": department.id,
        "department_name": department.department_name,
        "department_code": department.department_code,
        "quantity": row.quantity,
        "available_quantity": max(row.quantity - reserved, 0),
        "assembly_unit_quantity": (
            bom_item.pcs if bom_item else int(origin_node.get("output_pcs", 1))
        ),
        "delivery_date": order_item.delivery_date,
    }
