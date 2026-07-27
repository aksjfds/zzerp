from departments.base import DepartmentModuleApi
from departments.capabilities.quality import QualityCapability
from departments.capabilities.workforce import WorkforceCapability
from departments.contracts import (
    CAP_QUALITY,
    CAP_WORKERS,
    DepartmentDescriptor,
)


class QcDepartmentApi(
    WorkforceCapability,
    QualityCapability,
    DepartmentModuleApi,
):
    pass


API = QcDepartmentApi(
    DepartmentDescriptor(
        code="qc",
        name="QC部门",
        execution_module="quality",
        capabilities=frozenset({CAP_WORKERS, CAP_QUALITY}),
    )
)
