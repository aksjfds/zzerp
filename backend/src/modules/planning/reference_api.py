"""Product-level references; plans never reference an engineering version."""

from sqlalchemy import select
from sqlalchemy.orm import aliased

from modules.planning.persistence import DepartmentWorkOrder, DepartmentWorkOrderMovement, DepartmentHandoffTicket, ProductionPlanItem


def has_product_reference(session, product_id: int) -> bool:
    return session.scalar(
        select(ProductionPlanItem.production_plan_id).where(ProductionPlanItem.product_id == product_id).limit(1)
    ) is not None


def referenced_handoff_pairs(session, product_id: int):
    source, target = aliased(DepartmentWorkOrder), aliased(DepartmentWorkOrder)
    return set(session.execute(select(source.material_node_id, source.department_node_id,
        target.material_node_id, target.department_node_id).select_from(DepartmentHandoffTicket)
        .join(DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.id == DepartmentHandoffTicket.issue_movement_id)
        .join(source, source.id == DepartmentWorkOrderMovement.work_order_id)
        .join(target, target.id == DepartmentHandoffTicket.target_work_order_id)
        .where(source.product_id == product_id)).all())


def referenced_input_nodes(session, product_id: int):
    return set(session.scalars(select(DepartmentWorkOrderMovement.input_material_node_id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
        .where(DepartmentWorkOrder.product_id == product_id,
               DepartmentWorkOrderMovement.input_material_node_id.is_not(None))))


def referenced_route_pairs(session, product_id: int) -> set[tuple[str, str]]:
    return set(session.execute(select(DepartmentWorkOrder.material_node_id, DepartmentWorkOrder.department_node_id).where(
        DepartmentWorkOrder.product_id == product_id,
    )).all())
