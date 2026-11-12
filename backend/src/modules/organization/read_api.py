from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.persistence import ProductionDepartment


def department_names(session, codes: set[str] | None = None) -> dict[str, str]:
    statement = select(ProductionDepartment).order_by(ProductionDepartment.code)
    if codes is not None:
        if not codes:
            return {}
        statement = statement.where(ProductionDepartment.code.in_(codes))
    return {row.code: row.name for row in session.scalars(statement)}


def validate_departments(session, codes: set[str]) -> None:
    if set(department_names(session, codes)) != codes:
        raise DomainError("invalid_production_department", "部门节点引用的生产部门不存在", path="process_flow.nodes")
