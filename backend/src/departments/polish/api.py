from departments.base import DepartmentModuleApi
from departments.capabilities.printing import SpecialPrintingCapability
from departments.capabilities.repositories import RepositoryCapability
from departments.capabilities.standard_execution import StandardExecutionCapability
from departments.capabilities.work_orders import WorkOrderCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_REPOSITORIES,
    CAP_SPECIAL_PRINTING,
    CAP_STANDARD_EXECUTION,
    CAP_WORK_ORDERS,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class PolishDepartmentApi(
    RepositoryCapability,
    WorkOrderCapability,
    WorkforceCapability,
    StandardExecutionCapability,
    SpecialPrintingCapability,
    DepartmentModuleApi,
):
    pass


API = PolishDepartmentApi(
    DepartmentDescriptor(
        code="polish",
        name="表面处理部",
        execution_module="standard_execution",
        capabilities=frozenset(
            {
                CAP_REPOSITORIES,
                CAP_WORK_ORDERS,
                CAP_WORKERS,
                CAP_STANDARD_EXECUTION,
                CAP_SPECIAL_PRINTING,
            }
        ),
    )
)
