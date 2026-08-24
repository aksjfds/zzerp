from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from modules.engineering.model_api import Product, ProductBom
from modules.errors import DomainError
from modules.organization.model_api import Department, Procedure, Workshop
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.production_progress_arrivals import (
    calculate_progress_arrivals,
)
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.operational_api import load_product_flow
from modules.planning.production_progress_mapper import (
    build_department_progress_response,
)
from modules.planning.production_progress_routes import (
    _node_department_code,
    _node_workshop_name,
)
from modules.planning.progress_routes import progress_route_nodes
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.workforce.model_api import Worker


def get_department_production_progress_item(
    department_code: str,
    production_plan_item_id: int,
    processing_workshop: str | None = None,
    flow_node_id: str | None = None,
) -> dict:
    with SessionLocal() as session:
        plan_item = session.get(ProductionPlanItem, production_plan_item_id)
        if plan_item is None:
            raise DomainError(
                "production_plan_item_not_found",
                "生产计划明细不存在",
                status_code=404,
            )
        plan = session.get(ProductionPlan, plan_item.production_plan_id)
        order_item = session.get(CustomerOrderItem, plan_item.customer_order_item_id)
        order = session.get(CustomerOrder, plan.customer_order_id) if plan else None
        product = session.get(Product, plan_item.product_id)
        if plan is None or order_item is None or order is None or product is None:
            raise DomainError(
                "production_progress_context_missing",
                "生产计划关联数据不完整",
                status_code=409,
            )

        flow, nodes = load_product_flow(
            session,
            plan_item.product_id,
            plan_item.product_version,
        )
        route_nodes = progress_route_nodes(flow, nodes, plan_item.flow_node_id)
        procedures = {
            item.id: item for item in session.scalars(select(Procedure)).all()
        }
        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        departments = {
            item.id: item for item in session.scalars(select(Department)).all()
        }
        department_codes = {
            item.department_code: item for item in departments.values()
        }
        department_route_nodes = [
            node
            for node in route_nodes
            if _node_department_code(
                node,
                workshops,
                departments,
            ) == department_code
        ]
        if not department_route_nodes:
            raise DomainError(
                "production_progress_item_access_denied",
                "该生产任务不属于当前部门",
                status_code=403,
            )
        if flow_node_id:
            department_route_nodes = [
                node for node in department_route_nodes
                if node["id"] == flow_node_id
            ]
            if not department_route_nodes:
                raise DomainError(
                    "production_progress_node_not_found",
                    "当前生产任务节点不存在，请刷新后重试",
                    status_code=404,
                )
        if processing_workshop:
            department_route_nodes = [
                node
                for node in department_route_nodes
                if _node_workshop_name(
                    node,
                    workshops,
                ) == processing_workshop
            ]
            if not department_route_nodes:
                raise DomainError(
                    "production_progress_workshop_not_found",
                    "当前加工工艺不存在，请刷新后重试",
                    status_code=404,
                )

        route_node_ids = {node["id"] for node in route_nodes}
        order_production_items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id
                == plan_item.customer_order_item_id,
                ProductionItem.product_id == plan_item.product_id,
                ProductionItem.product_version == plan_item.product_version,
            )
        ).all())
        production_items = [
            item for item in order_production_items
            if item.origin_flow_node_id == plan_item.flow_node_id
            and (
                item.product_bom_id is None
                if plan_item.product_bom_id is None
                else item.product_bom_id == plan_item.product_bom_id
            )
        ]
        production_item_ids = {item.id for item in production_items}

        work_orders = list(session.scalars(
            select(WorkOrder)
            .where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrder.flow_node_id.in_(route_node_ids),
            )
            .order_by(WorkOrder.id.desc())
        ).all()) if route_node_ids and production_item_ids else []
        work_order_ids = {item.id for item in work_orders}
        work_order_by_id = {item.id: item for item in work_orders}
        batches = list(session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_(work_order_ids)
            )
        ).all()) if work_order_ids else []
        batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        for batch in batches:
            batches_by_order[batch.work_order_id].append(batch)

        worker_ids = {item.worker_id for item in work_orders if item.worker_id}
        workers = {
            item.id: item
            for item in session.scalars(
                select(Worker).where(Worker.id.in_(worker_ids))
            ).all()
        } if worker_ids else {}

        movement_items = (
            order_production_items
            if plan_item.item_type == "assembly"
            else production_items
        )
        movement_item_ids = {item.id for item in movement_items}
        movements = list(session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(movement_item_ids)
            )
        ).all()) if movement_item_ids else []
        bom_items = {
            item.id: item
            for item in session.scalars(
                select(ProductBom).where(
                    ProductBom.product_id == plan_item.product_id,
                    ProductBom.product_version == plan_item.product_version,
                )
            )
        } if plan_item.item_type == "assembly" else {}
        arrivals_by_node = calculate_progress_arrivals(
            plan_item=plan_item,
            flow=flow,
            nodes=nodes,
            route_node_ids=route_node_ids,
            order_production_items=order_production_items,
            movements=movements,
            work_order_by_id=work_order_by_id,
            bom_items=bom_items,
        )

        return build_department_progress_response(
            plan_item=plan_item,
            plan=plan,
            order=order,
            product=product,
            department_route_nodes=department_route_nodes,
            procedures=procedures,
            workshops=workshops,
            departments=departments,
            department_codes=department_codes,
            production_item_ids=production_item_ids,
            work_orders=work_orders,
            batches_by_order=batches_by_order,
            workers=workers,
            arrivals_by_node=arrivals_by_node,
        )


__all__ = ["get_department_production_progress_item"]
