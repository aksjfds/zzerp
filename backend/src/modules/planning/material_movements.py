"""Independent departmental receipts/issues and immutable movement history."""

from sqlalchemy import case, func, select

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from modules.engineering.route_api import current_route_references
from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.planning.persistence import DepartmentWorkOrder, DepartmentWorkOrderMovement
from modules.planning.queries import load_plan
from schemas.planning import DepartmentMovementCreate


def ensure_plan_without_movements(session, plan_id: int) -> None:
    exists = session.scalar(
        select(DepartmentWorkOrderMovement.id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
        .where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1)
    )
    if exists is not None:
        raise DomainError("plan_has_material_movements", "计划已有到料或出料流水，不能撤回、重建或删除工单", status_code=409)


def movement_totals(session, order_ids: set[int]) -> dict[int, tuple[str, str]]:
    if not order_ids:
        return {}
    rows = session.execute(select(
        DepartmentWorkOrderMovement.work_order_id,
        func.sum(case((DepartmentWorkOrderMovement.direction == "receipt", DepartmentWorkOrderMovement.quantity), else_=0)),
        func.sum(case((DepartmentWorkOrderMovement.direction == "issue", DepartmentWorkOrderMovement.quantity), else_=0)),
    ).where(DepartmentWorkOrderMovement.work_order_id.in_(order_ids))
      .group_by(DepartmentWorkOrderMovement.work_order_id))
    return {order_id: (str(int(received)), str(int(issued))) for order_id, received, issued in rows}


def load_scoped_order(session, order_id: int, department_scope: str | None):
    order = session.scalar(select(DepartmentWorkOrder).where(DepartmentWorkOrder.id == order_id)
                           .execution_options(populate_existing=True))
    if order is None:
        raise DomainError("department_work_order_not_found", "部门工单不存在", status_code=404)
    route = current_route_references(session, route_keys={
        (order.product_id, order.material_node_id, order.department_node_id),
    }).get((order.product_id, order.material_node_id, order.department_node_id))
    if route is None:
        raise DomainError("department_work_order_route_missing", "工单的当前路线不存在", status_code=409)
    if department_scope is not None and route.department_code != department_scope:
        raise DomainError("department_access_denied", "只能操作和查看本部门工单", status_code=403)
    return order


def serialize_movements(session, movements) -> list[dict]:
    names = usernames_by_ids(session, {row.actor_user_id for row in movements})
    return [{
        "id": row.id, "direction": row.direction, "quantity": row.quantity,
        "note": row.note, "request_id": row.request_id,
        "actor_username": names[row.actor_user_id],
        "created_at": row.created_at.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
    } for row in movements]


def record_movement(order_id: int, payload: DepartmentMovementCreate, *, department_scope: str | None, actor_user_id: int):
    if department_scope is None:
        raise DomainError("department_operator_required", "仅所属生产部门账号可登记到料和出料", status_code=403)
    with SessionLocal.begin() as session:
        order = load_scoped_order(session, order_id, department_scope)
        plan = load_plan(session, order.production_plan_id, for_update=True)
        order = load_scoped_order(session, order_id, department_scope)
        previous = session.scalar(select(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.work_order_id == order.id,
            DepartmentWorkOrderMovement.request_id == payload.request_id,
        ))
        if previous is not None:
            if (previous.direction, previous.quantity, previous.note, previous.actor_user_id) != (
                payload.direction, payload.quantity, payload.note, actor_user_id,
            ):
                raise DomainError("movement_request_conflict", "该提交标识已用于其他登记，请重新打开录入窗口", status_code=409)
            return serialize_movements(session, [previous])[0]
        if plan.status != "confirmed":
            raise DomainError("plan_not_open_for_movements", "仅已确认计划的工单允许登记到料和出料", status_code=409)
        movement = DepartmentWorkOrderMovement(
            work_order_id=order.id, actor_user_id=actor_user_id, **payload.model_dump(),
        )
        session.add(movement)
        session.flush()
        return serialize_movements(session, [movement])[0]


def list_movements(order_id: int, page: int, page_size: int, *, department_scope: str | None):
    with SessionLocal() as session:
        load_scoped_order(session, order_id, department_scope)
        condition = DepartmentWorkOrderMovement.work_order_id == order_id
        total = session.scalar(select(func.count()).select_from(DepartmentWorkOrderMovement).where(condition)) or 0
        movements = list(session.scalars(select(DepartmentWorkOrderMovement).where(condition)
            .order_by(func.date_trunc("second", DepartmentWorkOrderMovement.created_at).asc(),
                      DepartmentWorkOrderMovement.id.asc())
            .offset((page - 1) * page_size).limit(page_size)))
        return serialize_movements(session, movements), total
