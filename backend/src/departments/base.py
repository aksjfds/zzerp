from departments.contracts import DepartmentDescriptor
from modules.errors import DomainError


class DepartmentModuleApi:
    """Stable API shared by independently registered department modules."""

    def __init__(self, descriptor: DepartmentDescriptor) -> None:
        self.descriptor = descriptor

    def require_capability(self, capability: str) -> None:
        if not self.descriptor.supports(capability):
            raise DomainError(
                "department_capability_not_supported",
                f"部门“{self.descriptor.name}”不支持能力：{capability}",
                status_code=404,
            )

    def require_one_of(self, *capabilities: str) -> None:
        if not any(self.descriptor.supports(item) for item in capabilities):
            raise DomainError(
                "department_capability_not_supported",
                (
                    f"部门“{self.descriptor.name}”不支持能力："
                    f"{', '.join(capabilities)}"
                ),
                status_code=404,
            )
