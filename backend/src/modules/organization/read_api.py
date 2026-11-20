from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.persistence import ProductionDepartment

RECEIPT_DISABLED_CODES = frozenset({"stamp", "purchase", "qc"})


def operating_department(department_code):
    return 'warehouse' if department_code == 'purchase' else department_code


def allows_receipts(department_code: str) -> bool:
    return department_code not in RECEIPT_DISABLED_CODES


def allows_unreceived_issue(department_code: str) -> bool:
    return department_code == "stamp"


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
        raise DomainError("invalid_production_department", "部门节点引用的生产部门不存在", path="process_flow.nodes")


def requires_inspection(department_code: str) -> bool:
    return department_code == "qc"


def is_warehouse(department_code: str) -> bool:
    return department_code == 'warehouse'


def allows_manual_issue(department_code: str) -> bool:
    return not is_warehouse(department_code)


def allows_pick_history(department_code: str) -> bool:
    return department_code != 'stamp'
