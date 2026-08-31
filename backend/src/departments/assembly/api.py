from departments.base import DepartmentModuleApi
from departments.capabilities.assembly import AssemblyCapability
from departments.capabilities.production_progress import ProductionProgressCapability
from departments.capabilities.production_workbench import ProductionWorkbenchCapability
from departments.capabilities.standard_execution import StandardExecutionCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_ASSEMBLY,
    CAP_PRODUCTION_PROGRESS,
    CAP_PRODUCTION_WORKBENCH,
    CAP_STANDARD_EXECUTION,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class AssemblyDepartmentApi(
    ProductionProgressCapability,
    ProductionWorkbenchCapability,
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
                CAP_PRODUCTION_PROGRESS,
                CAP_PRODUCTION_WORKBENCH,
                CAP_WORKERS,
                CAP_STANDARD_EXECUTION,
                CAP_ASSEMBLY,
            }
        ),
    )
)
