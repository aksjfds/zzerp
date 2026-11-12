"""Product-level references; plans never reference an engineering version."""

from sqlalchemy import select

from modules.planning.persistence import DepartmentWorkOrder, ProductionPlan


def has_product_reference(session, product_id: int) -> bool:
    return session.scalar(
        select(ProductionPlan.id).where(ProductionPlan.product_id == product_id).limit(1)
    ) is not None


def referenced_route_pairs(session, product_id: int) -> set[tuple[str, str]]:
    return set(session.execute(select(DepartmentWorkOrder.material_node_id, DepartmentWorkOrder.department_node_id).where(
        DepartmentWorkOrder.product_id == product_id,
    )).all())
