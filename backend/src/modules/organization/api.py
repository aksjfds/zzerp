from database import SessionLocal

from modules.organization.read_api import (
    allows_receipts,
    department_names,
    is_warehouse,
    requires_inspection,
)


def list_departments(department_scope: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        codes = {department_scope} if department_scope is not None else None
        return [{"code": code, "name": name, "can_receive": allows_receipts(code), "requires_inspection": requires_inspection(code), "is_warehouse": is_warehouse(code)}
                for code, name in department_names(session, codes).items()]
