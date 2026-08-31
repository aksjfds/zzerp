"""Application-level dispatch for department-owned work-order creation."""

from departments.contracts import CAP_STANDARD_EXECUTION
from departments.registry import department_api
from departments.work_order_orchestration import create_work_order
from modules.errors import DomainError


def create_department_source_work_order(
    *,
    actor_department: str | None,
    actor_is_system: bool,
    repository_id: int,
    procedure_id: int | None,
    procedure_name: str | None,
    is_temporary: bool,
    quantity: int,
    worker_id: int | None,
    remark: str | None,
    actor_username: str,
) -> dict:
    if actor_is_system:
        return create_work_order(
            repository_id,
            procedure_id,
            procedure_name,
            is_temporary,
            quantity,
            worker_id,
            remark,
            actor_username,
            actor_department,
            actor_is_system,
        )
    if actor_department is None:
        raise DomainError(
            "department_access_denied",
            "账号未绑定部门",
            status_code=403,
        )
    return department_api(
        actor_department,
        CAP_STANDARD_EXECUTION,
    ).create_source_work_order(
        repository_id,
        procedure_id,
        procedure_name,
        is_temporary,
        quantity,
        worker_id,
        remark,
        actor_username,
    )


__all__ = ["create_department_source_work_order"]
