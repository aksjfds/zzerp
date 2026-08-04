from departments.base import DepartmentModuleApi
from departments.contracts import (
    CAP_FINISHED_GOODS,
    CAP_INVENTORY,
    DepartmentDescriptor,
)


class FinishedDepartmentApi(DepartmentModuleApi):
    pass


API = FinishedDepartmentApi(
    DepartmentDescriptor(
        code="finished",
        name="成品部",
        execution_module="finished_goods",
        capabilities=frozenset({
            CAP_FINISHED_GOODS,
            CAP_INVENTORY,
        }),
    )
)
