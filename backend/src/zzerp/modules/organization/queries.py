from sqlalchemy import select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.organization.persistence import ProductionDepartment


def allows_receipts(department_code: str) -> bool:
    return department_code not in {"stamp", "purchase"}


def uses_assembly_tree(department_code: str) -> bool:
    return department_code in {"laser", "assembly"}


def department_names(session, codes: set[str] | None = None) -> dict[str, str]:
    statement = select(ProductionDepartment).order_by(ProductionDepartment.code)
    if codes is not None:
        if not codes:
            return {}
        statement = statement.where(ProductionDepartment.code.in_(codes))
    return {row.code: row.name for row in session.scalars(statement)}


def validate_departments(session, codes: set[str]) -> None:
    if set(department_names(session, codes)) != codes:
        raise DomainError(
            "invalid_production_department",
            "部门节点引用的生产部门不存在",
            path="process_flow.nodes",
        )


def list_departments(session: Session, department_scope: str | None = None) -> list[dict]:
    codes = {department_scope} if department_scope is not None else None
    return [
        {"code": code, "name": name, "can_receive": allows_receipts(code)}
        for code, name in department_names(session, codes).items()
    ]
