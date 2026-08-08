from sqlalchemy import select

from database import SessionLocal
from domain.production_types import (
    MOVEMENT_QC_DISPATCH,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_PURCHASE_RECEIPT,
    WORK_ORDER_TAG,
)
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import WorkOrderContext
from modules.production_core.operational_api import (
    move_to_node,
    node_context,
    process_qc_node,
    record_movement,
    refresh_order_closed,
)
from modules.inventory.identity import inventory_identity_key
from modules.inventory.ownership_api import confirm_receipt, create_receipt
from modules.production_core.warehouse_storage import production_item_inventory_identity
from modules.production_core.qc_api import (
    dispatched_qc_quantity,
    load_qc_production_item,
    load_qc_work_order,
)
from modules.quality.persistence import WorkOrderBatch
from modules.standard_execution.tag_api import is_final_tag_set
from modules.engineering.model_api import Product
from modules.production_core.persistence import ProductionItem, WorkOrder
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


def list_closed_qc_surplus() -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(WorkOrderBatch, WorkOrder, ProductionItem, CustomerOrder, Product)
            .join(WorkOrder, WorkOrder.id == WorkOrderBatch.work_order_id)
            .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
            .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .join(Product, Product.id == ProductionItem.product_id)
            .where(
                CustomerOrder.status == "closed",
                WorkOrderBatch.recorded_at.is_not(None),
                WorkOrderBatch.qualified_quantity > 0,
            )
            .order_by(WorkOrderBatch.id)
        )
        result = []
        for batch, order, production_item, customer_order, product in rows:
            release = qc_release_context(session, batch, order)
            if release is None or release["dispatchable_quantity"] <= 0:
                continue
            context, completed_node = node_context(
                session, production_item, order.flow_node_id
            )
            item_type, item_code, item_name = production_item_inventory_identity(
                session, production_item
            )
            result.append({
                "key": f"qc:{batch.id}",
                "source_kind": "qc",
                "batch_id": batch.id,
                "production_item_id": production_item.id,
                "customer_order_no": customer_order.customer_order_no,
                "product_code": product.factory_code,
                "product_name": product.product_name,
                "product_version": production_item.product_version,
                "item_type": item_type,
                "item_code": item_code,
                "item_name": item_name,
                "department_code": "qc",
                "flow_node_id": release["qc_node"]["id"],
                "source_flow_node_id": completed_node["id"],
                "current_node_label": release["qc_node"].get(
                    "label", release["qc_node"]["id"]
                ),
                "completed_flow_node_id": completed_node["id"],
                "completed_node_label": completed_node.get(
                    "label", completed_node["id"]
                ),
                "quantity": release["dispatchable_quantity"],
            })
        return result


def qc_release_context(
    session,
    batch: WorkOrderBatch,
    order: WorkOrderContext,
    dispatched_quantity: int | None = None,
) -> dict | None:
    if batch.recorded_at is None or not batch.qualified_quantity:
        return None
    production_item = load_qc_production_item(session, order.production_item_id)
    if production_item is None:
        return None
    context, process_node = node_context(session, production_item, order.flow_node_id)
    qc_node = process_qc_node(context.flow, context.nodes, process_node["id"])
    if order.work_order_type == WORK_ORDER_TAG:
        if order.procedure_id is None or not is_final_tag_set(
            session,
            production_item,
            order.procedure_id,
            order.target_tag_set_id,
        ):
            return None
    elif order.work_order_type not in {
        WORK_ORDER_PURCHASE_RECEIPT,
        WORK_ORDER_ASSEMBLY,
    }:
        return None
    if qc_node is None:
        return None
    dispatched = dispatched_quantity
    if dispatched is None:
        dispatched = dispatched_qc_quantity(session, batch.id)
    target = context.normal_target(qc_node["id"])
    return {
        "production_item": production_item,
        "qc_node": qc_node,
        "target": target,
        "dispatchable_quantity": max(batch.qualified_quantity - int(dispatched), 0),
    }


def dispatch_qc_batch(
    batch_id: int,
    quantity: int,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "qc"}:
        raise DomainError("qc_access_denied", "只有QC可以放行合格数量", status_code=403)
    with SessionLocal.begin() as session:
        batch = session.get(WorkOrderBatch, batch_id, with_for_update=True)
        if batch is None:
            raise DomainError("qc_batch_not_found", "QC批次不存在", status_code=404)
        order = load_qc_work_order(
            session,
            batch.work_order_id,
            for_update=True,
        )
        if order is None:
            raise DomainError("work_order_not_found", "QC批次所属工单不存在", status_code=404)
        release = qc_release_context(session, batch, order)
        if release is None:
            raise DomainError("qc_batch_not_dispatchable", "当前批次不是可放行的最终工艺批次")
        if quantity <= 0 or quantity > release["dispatchable_quantity"]:
            raise DomainError("qc_dispatch_quantity_exceeded", "放行数量超过合格待放行数量")
        target = release["target"]
        if target is None:
            raise DomainError("qc_target_missing", "QC节点没有有效后续流程节点")
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        target_department_id = move_to_node(
            session,
            release["production_item"],
            target,
            quantity,
            release["qc_node"]["id"],
        )
        record_movement(
            session,
            production_item=release["production_item"],
            quantity=quantity,
            movement_type=MOVEMENT_QC_DISPATCH,
            source_flow_node_id=release["qc_node"]["id"],
            target_flow_node_id=target["id"],
            source_tag_set_id=order.target_tag_set_id,
            target_tag_set_id=None,
            source_department_id=qc_department_id,
            target_department_id=target_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        refresh_order_closed(session, release["production_item"])
        return {
            "batch_id": batch.id,
            "quantity": quantity,
            "remaining_quantity": release["dispatchable_quantity"] - quantity,
            "target_flow_node_id": target["id"],
            "target_department_id": target_department_id,
        }


def store_qc_batch_in_warehouse(
    batch_id: int,
    quantity: int,
    user_department: str,
    actor_username: str,
) -> dict:
    if user_department not in {"sys", "qc"}:
        raise DomainError("qc_access_denied", "只有QC可以将合格物料存入仓库", status_code=403)
    with SessionLocal.begin() as session:
        batch = session.get(WorkOrderBatch, batch_id, with_for_update=True)
        if batch is None:
            raise DomainError("qc_batch_not_found", "QC批次不存在", status_code=404)
        order = load_qc_work_order(session, batch.work_order_id, for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "QC批次所属工单不存在", status_code=404)
        release = qc_release_context(session, batch, order)
        if release is None or quantity <= 0 or quantity > release["dispatchable_quantity"]:
            raise DomainError("qc_warehouse_quantity_exceeded", "入库数量超过合格待放行数量")
        production_item = release["production_item"]
        context, completed_node = node_context(session, production_item, order.flow_node_id)
        customer_order = session.get(CustomerOrder, context.order_item.customer_order_id)
        if customer_order is None or customer_order.status != "closed":
            raise DomainError(
                "qc_warehouse_order_not_closed",
                "客户订单结单后才能将合格结余存入仓库",
                status_code=409,
            )
        item_type, item_code, item_name = production_item_inventory_identity(
            session, production_item
        )
        receipt = create_receipt(
            session,
            identity_key=inventory_identity_key(
                department_code="warehouse",
                item_type=item_type,
                product_id=production_item.product_id,
                product_version=production_item.product_version,
                product_bom_id=production_item.product_bom_id,
                flow_node_id=production_item.origin_flow_node_id,
                completed_flow_node_id=completed_node["id"],
            ),
            department_code="warehouse",
            item_type=item_type,
            product_id=production_item.product_id,
            product_version=production_item.product_version,
            product_bom_id=production_item.product_bom_id,
            flow_node_id=production_item.origin_flow_node_id,
            completed_flow_node_id=completed_node["id"],
            item_code=item_code,
            item_name=item_name,
            quantity=quantity,
            source_customer_order_id=context.order_item.customer_order_id,
            source_production_item_id=production_item.id,
        )
        stock = confirm_receipt(
            session, receipt.id, actor_username, "QC合格物料存入仓库"
        )
        department_ids = get_department_ids_by_codes(session, {"qc", "warehouse"})
        if "qc" not in department_ids or "warehouse" not in department_ids:
            raise DomainError("department_not_found", "QC或仓库部门不存在")
        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type=MOVEMENT_QC_DISPATCH,
            source_flow_node_id=release["qc_node"]["id"],
            target_flow_node_id=release["qc_node"]["id"],
            source_tag_set_id=order.target_tag_set_id,
            target_tag_set_id=None,
            source_department_id=department_ids["qc"],
            target_department_id=department_ids["warehouse"],
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        refresh_order_closed(session, production_item, actor_username)
        return {
            "inventory_stock_id": stock.id,
            "quantity": quantity,
            "completed_flow_node_id": completed_node["id"],
            "completed_node_label": completed_node.get("label", completed_node["id"]),
        }
