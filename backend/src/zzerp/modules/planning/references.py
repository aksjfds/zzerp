"""Product base references and appearance-scoped production history protection."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from zzerp.modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    ProductionPlanItem,
)


def has_product_reference(session: Session, product_id: int) -> bool:
    return (
        session.scalar(
            select(ProductionPlanItem.production_plan_id)
            .where(ProductionPlanItem.product_id == product_id)
            .limit(1)
        )
        is not None
    )


def referenced_handoff_pairs(
    session: Session, product_id: int, appearance_id: int | None = None
) -> set[tuple[str, str, str, str]]:
    source, target = aliased(DepartmentWorkOrder), aliased(DepartmentWorkOrder)
    rows = session.execute(
        select(
            source.material_node_id,
            source.department_node_id,
            target.material_node_id,
            target.department_node_id,
        )
        .select_from(DepartmentHandoffTicket)
        .join(
            DepartmentWorkOrderMovement,
            DepartmentWorkOrderMovement.id == DepartmentHandoffTicket.issue_movement_id,
        )
        .join(source, source.id == DepartmentWorkOrderMovement.work_order_id)
        .join(target, target.id == DepartmentHandoffTicket.target_work_order_id)
        .where(
            source.product_id == product_id,
            source.appearance_id == appearance_id if appearance_id is not None else True,
        )
    )
    return {(sm, sd, tm, td) for sm, sd, tm, td in rows}


def referenced_input_nodes(
    session: Session, product_id: int, appearance_id: int | None = None
) -> set[str]:
    return set(
        session.scalars(
            select(DepartmentWorkOrderMovement.input_material_node_id)
            .join(
                DepartmentWorkOrder,
                DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id,
            )
            .where(
                DepartmentWorkOrder.product_id == product_id,
                DepartmentWorkOrder.appearance_id == appearance_id
                if appearance_id is not None
                else True,
                DepartmentWorkOrderMovement.input_material_node_id.is_not(None),
            )
        )
    )


def referenced_route_pairs(
    session: Session, product_id: int, appearance_id: int | None = None
) -> set[tuple[str, str]]:
    rows = session.execute(
        select(DepartmentWorkOrder.material_node_id, DepartmentWorkOrder.department_node_id).where(
            DepartmentWorkOrder.product_id == product_id,
            DepartmentWorkOrder.appearance_id == appearance_id
            if appearance_id is not None
            else True,
        )
    )
    return {(material_id, department_id) for material_id, department_id in rows}
