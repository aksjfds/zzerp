from database import SessionLocal
from modules.organization.read_api import department_names


def list_departments(department_scope: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        codes = {department_scope} if department_scope is not None else None
        return [{"code": code, "name": name} for code, name in department_names(session, codes).items()]
