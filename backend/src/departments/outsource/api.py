from departments.base import DepartmentModuleApi
from departments.capabilities.production_progress import ProductionProgressCapability
from departments.capabilities.production_workbench import ProductionWorkbenchCapability
from departments.capabilities.standard_execution import StandardExecutionCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_PRODUCTION_PROGRESS,
    CAP_PRODUCTION_WORKBENCH,
    CAP_STANDARD_EXECUTION,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class OutsourceDepartmentApi(
    ProductionProgressCapability,
    ProductionWorkbenchCapability,
    WorkforceCapability,
    StandardExecutionCapability,
    DepartmentModuleApi,
):
    pass


API = OutsourceDepartmentApi(
    DepartmentDescriptor(
        code="outsource",
        name="外协部",
        execution_module="standard_execution",
        capabilities=frozenset(
            {
                CAP_PRODUCTION_PROGRESS,
                CAP_PRODUCTION_WORKBENCH,
                CAP_WORKERS,
                CAP_STANDARD_EXECUTION,
            }
        ),
    )
)
