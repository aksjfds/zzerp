"""Stable planning task contexts for supplier-processing workflows."""

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.production_types import WorkOrderStatus
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.planning.persistence import (
    ProductionPlan,
    ProductionPlanItem,
    ProductionRouteTask,
)
from modules.production_core.reference_api import (
    PartProductionIdentity,
    part_production_references,
    supplier_processing_work_order_references,
)

SUPPLIER_PROCESSING_PLAN_STATUSES = frozenset({"confirmed", "completed"})


@dataclass(frozen=True, slots=True)
class SupplierProcessingTaskContext:
    production_plan_id: int
    production_plan_item_id: int
    production_item_id: int | None
    customer_order_item_id: int
    product_id: int
    product_version: int
    product_bom_id: int
    source_flow_node_id: str
    supplier_flow_node_id: str
    department_id: int
    item_code: str
    item_name: str
    task_quantity: int
    plan_status: str
    work_order_id: int | None
    work_order_status: WorkOrderStatus | None
    can_create_work_order: bool


def list_supplier_processing_tasks(
    session: Session,
    *,
    production_plan_id: int | None = None,
) -> list[SupplierProcessingTaskContext]:
    rows = _task_rows(
        session,
        production_plan_id=production_plan_id,
        plan_statuses=SUPPLIER_PROCESSING_PLAN_STATUSES,
    )
    return _task_contexts(session, rows)


def require_supplier_processing_task_for_creation(
    session: Session,
    *,
    production_plan_item_id: int,
    supplier_flow_node_id: str,
) -> SupplierProcessingTaskContext:
    rows = _task_rows(
        session,
        production_plan_item_id=production_plan_item_id,
        supplier_flow_node_id=supplier_flow_node_id,
        lock_plan=True,
    )
    if not rows:
        raise DomainError(
            "supplier_processing_task_not_found",
            "委外加工任务不存在",
            status_code=404,
        )
    if len(rows) != 1:
        raise DomainError(
            "supplier_processing_task_ambiguous",
            "委外加工任务身份不唯一",
            status_code=409,
        )
    task = _task_contexts(session, rows)[0]
    if task.plan_status not in SUPPLIER_PROCESSING_PLAN_STATUSES:
        raise DomainError(
            "supplier_processing_plan_not_confirmed",
            "生产计划必须已经确认且未取消，才能创建委外加工工单",
            status_code=409,
        )
    if task.production_item_id is None:
        raise DomainError(
            "supplier_processing_material_missing",
            "委外加工任务缺少对应的生产物料",
            status_code=409,
        )
    if task.task_quantity <= 0:
        raise DomainError(
            "supplier_processing_quantity_invalid",
            "委外加工任务数量必须大于 0",
            status_code=409,
        )
    if task.work_order_id is not None:
        raise DomainError(
            "supplier_processing_work_order_exists",
            "该委外加工任务已经创建工单",
            status_code=409,
        )
    return task


def _task_rows(
    session: Session,
    *,
    production_plan_id: int | None = None,
    production_plan_item_id: int | None = None,
    supplier_flow_node_id: str | None = None,
    plan_statuses: Collection[str] | None = None,
    lock_plan: bool = False,
):
    statement = (
        select(ProductionPlan, ProductionPlanItem, ProductionRouteTask)
        .join(
            ProductionPlanItem,
            ProductionPlanItem.production_plan_id == ProductionPlan.id,
        )
        .join(
            ProductionRouteTask,
            ProductionRouteTask.production_plan_item_id == ProductionPlanItem.id,
        )
        .where(
            ProductionPlanItem.item_type == "part",
            ProductionRouteTask.route_node_type == "supplier_processing",
        )
        .order_by(
            ProductionPlan.id,
            ProductionPlanItem.sort_order,
            ProductionRouteTask.route_order,
        )
    )
    if production_plan_id is not None:
        statement = statement.where(ProductionPlan.id == production_plan_id)
    if plan_statuses is not None:
        if not plan_statuses:
            return []
        statement = statement.where(ProductionPlan.status.in_(list(plan_statuses)))
    if production_plan_item_id is not None:
        statement = statement.where(
            ProductionPlanItem.id == production_plan_item_id
        )
    if supplier_flow_node_id is not None:
        statement = statement.where(
            ProductionRouteTask.route_flow_node_id == supplier_flow_node_id
        )
    if lock_plan:
        statement = statement.with_for_update(of=ProductionPlan)
    return list(session.execute(statement))


def _task_contexts(session: Session, rows) -> list[SupplierProcessingTaskContext]:
    if not rows:
        return []
    business_department_id = get_department_ids_by_codes(
        session,
        {"business"},
    ).get("business")
    if business_department_id is None:
        raise DomainError("department_not_found", "业务部不存在", status_code=409)

    identities: set[PartProductionIdentity] = set()
    for _plan, item, route in rows:
        if item.product_bom_id is None:
            raise DomainError(
                "supplier_processing_part_invalid",
                "委外加工任务没有绑定普通配件",
                status_code=409,
            )
        if route.department_id != business_department_id:
            raise DomainError(
                "supplier_processing_department_invalid",
                "委外加工任务没有归属业务部",
                status_code=409,
            )
        identities.add(_part_identity(item))

    production_references = part_production_references(session, identities)
    positions = {
        (reference.id, route.route_flow_node_id)
        for _plan, item, route in rows
        if (reference := production_references.get(_part_identity(item))) is not None
    }
    order_references = supplier_processing_work_order_references(
        session,
        positions,
    )

    result: list[SupplierProcessingTaskContext] = []
    for plan, item, route in rows:
        production_reference = production_references.get(_part_identity(item))
        if plan.status in {"confirmed", "completed"} and production_reference is None:
            raise DomainError(
                "supplier_processing_material_missing",
                "已确认的委外加工任务缺少对应生产物料",
                status_code=409,
            )
        order_reference = (
            order_references.get(
                (production_reference.id, route.route_flow_node_id)
            )
            if production_reference is not None
            else None
        )
        result.append(SupplierProcessingTaskContext(
            production_plan_id=plan.id,
            production_plan_item_id=item.id,
            production_item_id=(
                production_reference.id if production_reference is not None else None
            ),
            customer_order_item_id=item.customer_order_item_id,
            product_id=item.product_id,
            product_version=item.product_version,
            product_bom_id=item.product_bom_id,
            source_flow_node_id=item.flow_node_id,
            supplier_flow_node_id=route.route_flow_node_id,
            department_id=route.department_id,
            item_code=item.item_code,
            item_name=item.item_name,
            task_quantity=item.planned_production_quantity,
            plan_status=plan.status,
            work_order_id=order_reference.id if order_reference else None,
            work_order_status=order_reference.status if order_reference else None,
            can_create_work_order=(
                plan.status in SUPPLIER_PROCESSING_PLAN_STATUSES
                and item.planned_production_quantity > 0
                and production_reference is not None
                and order_reference is None
            ),
        ))
    return result


def _part_identity(item: ProductionPlanItem) -> PartProductionIdentity:
    if item.product_bom_id is None:
        raise DomainError(
            "supplier_processing_part_invalid",
            "委外加工任务没有绑定普通配件",
            status_code=409,
        )
    return (
        item.customer_order_item_id,
        item.product_id,
        item.product_version,
        item.product_bom_id,
        item.flow_node_id,
    )


__all__ = [
    "SUPPLIER_PROCESSING_PLAN_STATUSES",
    "SupplierProcessingTaskContext",
    "list_supplier_processing_tasks",
    "require_supplier_processing_task_for_creation",
]
