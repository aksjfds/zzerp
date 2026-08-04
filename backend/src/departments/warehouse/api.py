from departments.base import DepartmentModuleApi
from departments.contracts import CAP_INVENTORY, DepartmentDescriptor


class WarehouseDepartmentApi(DepartmentModuleApi):
    pass


API = WarehouseDepartmentApi(
    DepartmentDescriptor(
        code="warehouse",
        name="仓库",
        execution_module="inventory",
        capabilities=frozenset({CAP_INVENTORY}),
    )
)
