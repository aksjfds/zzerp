"""Deterministic plan-item to department route projection."""

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from modules.engineering.model_api import ProductProcessFlow
from modules.errors import DomainError
from modules.organization.model_api import Workshop
from modules.organization.read_api import get_department_ids_by_codes
from modules.planning.persistence import (
    ProductionPlan,
    ProductionRouteTask,
)
from modules.production_core.flow_api import physical_route_nodes


def rebuild_plan_route_tasks(session: Session, plan: ProductionPlan) -> None:
    session.execute(
        delete(ProductionRouteTask).where(
            ProductionRouteTask.production_plan_id == plan.id
        )
    )
    route_items = [
        item for item in plan.items if item.item_type in {"part", "assembly"}
    ]
    if not route_items:
        return

    flow_keys = {(item.product_id, item.product_version) for item in route_items}
    flow_records = {
        (record.product_id, record.product_version): record
        for record in session.scalars(
            select(ProductProcessFlow).where(
                tuple_(
                    ProductProcessFlow.product_id,
                    ProductProcessFlow.product_version,
                ).in_(flow_keys)
            )
        )
    }
    workshop_ids: set[int] = set()
    projected_nodes: dict[int, list[tuple[int, dict]]] = {}
    for item in route_items:
        flow_record = flow_records.get((item.product_id, item.product_version))
        if flow_record is None:
            raise DomainError(
                "product_engineering_data_missing",
                "生产计划绑定的产品版本缺少正式流程图",
            )
        flow = flow_record.flow_json
        nodes = {node["id"]: node for node in flow.get("nodes", [])}
        execution_nodes = [
            (route_order, node)
            for route_order, node in enumerate(
                physical_route_nodes(flow, nodes, item.flow_node_id)
            )
            if node.get("type") in {
                "process",
                "assembly",
                "supplier_processing",
            }
        ]
        projected_nodes[item.id] = execution_nodes
        workshop_ids.update(
            int(node["workshop_id"])
            for _route_order, node in execution_nodes
            if node.get("workshop_id") is not None
        )

    workshops = (
        {
            workshop.id: workshop
            for workshop in session.scalars(
                select(Workshop).where(Workshop.id.in_(workshop_ids))
            )
        }
        if workshop_ids
        else {}
    )
    has_supplier_processing = any(
        node.get("type") == "supplier_processing"
        for nodes in projected_nodes.values()
        for _route_order, node in nodes
    )
    business_department_id = (
        get_department_ids_by_codes(session, {"business"}).get("business")
        if has_supplier_processing
        else None
    )
    if has_supplier_processing and business_department_id is None:
        raise DomainError("flow_department_missing", "流程所需部门不存在：business")

    for item in route_items:
        for route_order, node in projected_nodes[item.id]:
            if node.get("type") == "supplier_processing":
                workshop_id = None
                department_id = business_department_id
            else:
                workshop = workshops.get(node.get("workshop_id"))
                if workshop is None:
                    raise DomainError(
                        "process_workshop_invalid",
                        f"流程节点“{node.get('label') or node['id']}”引用的车间不存在",
                        element_id=node["id"],
                    )
                workshop_id = workshop.id
                department_id = workshop.department_id
            if department_id is None:
                raise DomainError("flow_department_missing", "流程执行部门不存在")
            session.add(
                ProductionRouteTask(
                    production_plan_id=plan.id,
                    production_plan_item_id=item.id,
                    route_flow_node_id=node["id"],
                    route_node_type=node["type"],
                    workshop_id=workshop_id,
                    department_id=department_id,
                    route_order=route_order,
                )
            )
    session.flush()


__all__ = ["rebuild_plan_route_tasks"]
