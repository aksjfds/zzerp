from departments.base import DepartmentModuleApi
from departments.capabilities.repositories import RepositoryCapability
from departments.capabilities.production_progress import ProductionProgressCapability
from departments.capabilities.standard_execution import StandardExecutionCapability
from departments.capabilities.work_orders import WorkOrderCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_REPOSITORIES,
    CAP_PRODUCTION_PROGRESS,
    CAP_STANDARD_EXECUTION,
    CAP_WORK_ORDERS,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class CncDepartmentApi(
    ProductionProgressCapability,
    RepositoryCapability,
    WorkOrderCapability,
    WorkforceCapability,
    StandardExecutionCapability,
    DepartmentModuleApi,
):
    pass


API = CncDepartmentApi(
    DepartmentDescriptor(
        code="cnc",
        name="机加部",
        execution_module="standard_execution",
        capabilities=frozenset(
            {
                CAP_REPOSITORIES,
                CAP_PRODUCTION_PROGRESS,
                CAP_WORK_ORDERS,
                CAP_WORKERS,
                CAP_STANDARD_EXECUTION,
            }
        ),
    )
)
