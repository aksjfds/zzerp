from departments.assembly.api import API as ASSEMBLY
from departments.cnc.api import API as CNC
from departments.finished.api import API as FINISHED
from departments.outsource.api import API as OUTSOURCE
from departments.polish.api import API as POLISH
from departments.purchasing.api import API as PURCHASING
from departments.qc.api import API as QC
from departments.stamp.api import API as STAMP
from departments.warehouse.api import API as WAREHOUSE
from modules.errors import DomainError


DEPARTMENT_MODULES = {
    module.descriptor.code: module
    for module in (
        STAMP,
        CNC,
        POLISH,
        OUTSOURCE,
        PURCHASING,
        FINISHED,
        WAREHOUSE,
        ASSEMBLY,
        QC,
    )
}


def department_manifests() -> list[dict]:
    return [
        {
            "code": module.descriptor.code,
            "name": module.descriptor.name,
            "execution_module": module.descriptor.execution_module,
            "capabilities": sorted(module.descriptor.capabilities),
        }
        for module in DEPARTMENT_MODULES.values()
    ]


def department_api(
    department_code: str,
    required_capability: str | None = None,
):
    try:
        module = DEPARTMENT_MODULES[department_code]
    except KeyError as exc:
        raise DomainError(
            "department_module_not_found",
            f"生产部门模块不存在：{department_code}",
            status_code=404,
        ) from exc
    if required_capability is not None:
        module.require_capability(required_capability)
    return module


def department_api_for_any(
    department_code: str,
    required_capabilities: tuple[str, ...],
):
    module = department_api(department_code)
    module.require_one_of(*required_capabilities)
    return module
