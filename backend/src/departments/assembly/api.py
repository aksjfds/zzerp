from departments.base import DepartmentModuleApi
from departments.capabilities.assembly import AssemblyCapability
from departments.capabilities.repositories import RepositoryCapability
from departments.capabilities.production_progress import ProductionProgressCapability
from departments.capabilities.standard_execution import StandardExecutionCapability
from departments.capabilities.work_orders import WorkOrderCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_ASSEMBLY,
    CAP_REPOSITORIES,
    CAP_PRODUCTION_PROGRESS,
    CAP_STANDARD_EXECUTION,
    CAP_WORK_ORDERS,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class AssemblyDepartmentApi(
    ProductionProgressCapability,
    RepositoryCapability,
    WorkOrderCapability,
    WorkforceCapability,
    StandardExecutionCapability,
    AssemblyCapability,
    DepartmentModuleApi,
):
    pass


API = AssemblyDepartmentApi(
    DepartmentDescriptor(
        code="assembly",
        name="装配部",
        execution_module="assembly",
        capabilities=frozenset(
            {
                CAP_REPOSITORIES,
                CAP_PRODUCTION_PROGRESS,
                CAP_WORK_ORDERS,
                CAP_WORKERS,
                CAP_STANDARD_EXECUTION,
                CAP_ASSEMBLY,
            }
        ),
    )
)
