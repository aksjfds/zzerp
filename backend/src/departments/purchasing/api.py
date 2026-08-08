from departments.base import DepartmentModuleApi
from departments.capabilities.production_progress import ProductionProgressCapability
from departments.capabilities.purchasing import PurchasingCapability
from departments.capabilities.repositories import RepositoryCapability
from departments.capabilities.work_orders import WorkOrderCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_PRODUCTION_PROGRESS,
    CAP_PURCHASING,
    CAP_REPOSITORIES,
    CAP_WORK_ORDERS,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class PurchasingDepartmentApi(
    ProductionProgressCapability,
    RepositoryCapability,
    WorkOrderCapability,
    WorkforceCapability,
    PurchasingCapability,
    DepartmentModuleApi,
):
    pass


API = PurchasingDepartmentApi(
    DepartmentDescriptor(
        code="purchasing",
        name="采购部",
        execution_module="purchasing",
        capabilities=frozenset(
            {
                CAP_PRODUCTION_PROGRESS,
                CAP_PURCHASING,
                CAP_REPOSITORIES,
                CAP_WORK_ORDERS,
                CAP_WORKERS,
            }
        ),
    )
)
