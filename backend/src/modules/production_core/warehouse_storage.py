"""Store physical parts or assemblies from their current production node."""

from sqlalchemy import select

from database import SessionLocal
from modules.engineering.model_api import Product, ProductBom
from modules.errors import DomainError
from modules.inventory.identity import inventory_identity_key
from modules.inventory.ownership_api import confirm_receipt, create_receipt
from modules.organization.model_api import Department
from modules.production_core.card_status import reserved_quantities, reserved_tag_quantities
from modules.production_core.flow import load_production_flow
from modules.production_core.persistence import ProductionItem, Repository
from modules.production_core.work_order_presenters import production_item_name
from modules.production_core.work_order_support import consume_repository, refresh_order_closed
from modules.standard_execution.model_api import ProcedureTagStock
from modules.standard_execution.tags import consume_tag_stock
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


def list_closed_surplus_positions(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        department = session.scalar(select(Department).where(
            Department.department_code == department_code
        ))
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        repositories = list(session.scalars(
            select(Repository)
            .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
            .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .where(
                Repository.department_id == department.id,
                CustomerOrder.status == "closed",
            )
            .order_by(Repository.id)
        ))
        tag_stocks = list(session.scalars(
            select(ProcedureTagStock)
            .join(
                ProductionItem,
                ProductionItem.id == ProcedureTagStock.production_item_id,
            )
            .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .where(
                ProcedureTagStock.department_id == department.id,
                CustomerOrder.status == "closed",
            )
            .order_by(ProcedureTagStock.id)
        ))
        repository_reserved = reserved_quantities(
            session, [item.id for item in repositories]
        )
        tag_reserved = reserved_tag_quantities(
            session, [item.id for item in tag_stocks]
        )
        grouped: dict[tuple[int, str, str], int] = {}
        for item in repositories:
            key = (item.production_item_id, item.flow_node_id, item.source_flow_node_id)
            grouped[key] = grouped.get(key, 0) + max(
                item.quantity - repository_reserved.get(item.id, 0), 0
            )
        for item in tag_stocks:
            key = (item.production_item_id, item.flow_node_id, item.source_flow_node_id)
            grouped[key] = grouped.get(key, 0) + max(
                item.quantity - tag_reserved.get(item.id, 0), 0
            )
        return [
            _serialize_closed_position(session, department_code, key, quantity)
            for key, quantity in grouped.items()
            if quantity > 0
        ]


def _serialize_closed_position(
    session,
    department_code: str,
    key: tuple[int, str, str],
    quantity: int,
) -> dict:
    production_item_id, flow_node_id, source_flow_node_id = key
    production_item = session.get(ProductionItem, production_item_id)
    context = load_production_flow(session, production_item)
    order = session.get(CustomerOrder, context.order_item.customer_order_id)
    product = session.get(Product, production_item.product_id)
    item_type, item_code, item_name = production_item_inventory_identity(
        session, production_item
    )
    completed_node_id = _completed_node_id(
        context.flow, context.nodes, source_flow_node_id
    )
    return {
        "key": f"position:{production_item_id}:{flow_node_id}:{source_flow_node_id}",
        "source_kind": "production",
        "batch_id": None,
        "production_item_id": production_item_id,
        "customer_order_no": order.customer_order_no,
        "product_code": product.factory_code,
        "product_name": product.product_name,
        "product_version": production_item.product_version,
        "item_type": item_type,
        "item_code": item_code,
        "item_name": item_name,
        "department_code": department_code,
        "flow_node_id": flow_node_id,
        "source_flow_node_id": source_flow_node_id,
        "current_node_label": context.nodes.get(flow_node_id, {}).get("label", flow_node_id),
        "completed_flow_node_id": completed_node_id,
        "completed_node_label": context.nodes.get(completed_node_id, {}).get(
            "label", completed_node_id
        ),
        "quantity": quantity,
    }


def store_position_in_warehouse(
    department_code: str,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    quantity: int,
    actor_username: str,
) -> dict:
    if quantity <= 0:
        raise DomainError("warehouse_storage_quantity_invalid", "入库数量必须大于0")
    with SessionLocal.begin() as session:
        department = session.scalar(select(Department).where(
            Department.department_code == department_code
        ))
        production_item = session.get(ProductionItem, production_item_id, with_for_update=True)
        if department is None or production_item is None:
            raise DomainError("warehouse_storage_source_missing", "当前生产位置不存在", status_code=404)
        context = load_production_flow(session, production_item)
        customer_order = session.get(CustomerOrder, context.order_item.customer_order_id)
        if customer_order is None or customer_order.status != "closed":
            raise DomainError(
                "warehouse_storage_order_not_closed",
                "客户订单结单后才能将多余物料存入仓库",
                status_code=409,
            )
        current_node = context.nodes.get(flow_node_id)
        if current_node is None:
            raise DomainError("warehouse_storage_node_invalid", "当前流程节点不存在", status_code=409)
        repositories = list(session.scalars(
            select(Repository).where(
                Repository.production_item_id == production_item.id,
                Repository.flow_node_id == flow_node_id,
                Repository.source_flow_node_id == source_flow_node_id,
                Repository.department_id == department.id,
            ).order_by(Repository.id).with_for_update()
        ))
        tag_stocks = list(session.scalars(
            select(ProcedureTagStock).where(
                ProcedureTagStock.production_item_id == production_item.id,
                ProcedureTagStock.flow_node_id == flow_node_id,
                ProcedureTagStock.source_flow_node_id == source_flow_node_id,
                ProcedureTagStock.department_id == department.id,
            ).order_by(ProcedureTagStock.id).with_for_update()
        ))
        repository_reserved = reserved_quantities(session, [item.id for item in repositories])
        tag_reserved = reserved_tag_quantities(session, [item.id for item in tag_stocks])
        available = sum(
            max(item.quantity - repository_reserved.get(item.id, 0), 0)
            for item in repositories
        ) + sum(
            max(item.quantity - tag_reserved.get(item.id, 0), 0)
            for item in tag_stocks
        )
        if quantity > available:
            raise DomainError(
                "warehouse_storage_quantity_exceeds_available",
                f"最多可存入仓库 {available} 件",
                status_code=409,
            )

        completed_node_id = _completed_node_id(context.flow, context.nodes, source_flow_node_id)
        item_type, item_code, item_name = production_item_inventory_identity(session, production_item)
        receipt = create_receipt(
            session,
            identity_key=inventory_identity_key(
                department_code="warehouse",
                item_type=item_type,
                product_id=production_item.product_id,
                product_version=production_item.product_version,
                product_bom_id=production_item.product_bom_id,
                flow_node_id=production_item.origin_flow_node_id,
                completed_flow_node_id=completed_node_id,
            ),
            department_code="warehouse",
            item_type=item_type,
            product_id=production_item.product_id,
            product_version=production_item.product_version,
            product_bom_id=production_item.product_bom_id,
            flow_node_id=production_item.origin_flow_node_id,
            completed_flow_node_id=completed_node_id,
            item_code=item_code,
            item_name=item_name,
            quantity=quantity,
            source_customer_order_id=context.order_item.customer_order_id,
            source_production_item_id=production_item.id,
        )
        remaining = quantity
        for repository in repositories:
            allocated = min(
                max(repository.quantity - repository_reserved.get(repository.id, 0), 0),
                remaining,
            )
            if allocated:
                consume_repository(session, repository, allocated)
                remaining -= allocated
            if not remaining:
                break
        if remaining:
            for stock in tag_stocks:
                allocated = min(
                    max(stock.quantity - tag_reserved.get(stock.id, 0), 0),
                    remaining,
                )
                if allocated:
                    consume_tag_stock(session, stock, allocated)
                    remaining -= allocated
                if not remaining:
                    break
        warehouse_stock = confirm_receipt(
            session, receipt.id, actor_username, "生产节点存入仓库"
        )
        session.flush()
        refresh_order_closed(session, production_item, actor_username)
        return {
            "inventory_stock_id": warehouse_stock.id,
            "quantity": quantity,
            "completed_flow_node_id": completed_node_id,
            "completed_node_label": context.nodes.get(completed_node_id, {}).get("label", completed_node_id),
        }


def _completed_node_id(flow: dict, nodes: dict[str, dict], source_node_id: str) -> str:
    source = nodes.get(source_node_id)
    if source is None:
        raise DomainError("warehouse_storage_state_invalid", "无法确定物料完成状态", status_code=409)
    if source.get("type") != "qc":
        return source_node_id
    incoming = [
        edge.get("source_node_id")
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == source_node_id
    ]
    if len(incoming) != 1 or incoming[0] not in nodes:
        raise DomainError("warehouse_storage_state_invalid", "无法确定 QC 对应的完成节点", status_code=409)
    return incoming[0]


def production_item_inventory_identity(
    session,
    production_item: ProductionItem,
) -> tuple[str, str, str]:
    if production_item.product_bom_id is not None:
        bom = session.get(ProductBom, production_item.product_bom_id)
        if bom is None:
            raise DomainError("warehouse_storage_item_invalid", "配件资料不存在", status_code=409)
        return "part", bom.part_no, bom.part_name
    name = production_item_name(session, production_item, set())
    origin = load_production_flow(session, production_item).nodes.get(
        production_item.origin_flow_node_id, {}
    )
    code = origin.get("assembly_code") or name
    return "assembly", code, name


__all__ = [
    "list_closed_surplus_positions",
    "production_item_inventory_identity",
    "store_position_in_warehouse",
]
