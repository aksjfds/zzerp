from departments.contracts import CAP_ASSEMBLY
from modules.assembly import api as assembly


class AssemblyCapability:
    def create_assembly_work_order(
        self,
        repository_ids: list[int],
        quantity: int,
        worker_id: int | None,
        remark: str | None,
        actor_department: str,
    ) -> dict:
        self.require_capability(CAP_ASSEMBLY)
        return assembly.create_assembly_work_order(
            repository_ids,
            quantity,
            worker_id,
            remark,
            actor_department,
        )
