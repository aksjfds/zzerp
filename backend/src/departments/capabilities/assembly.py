from departments.contracts import CAP_ASSEMBLY
from modules.assembly import api as assembly


class AssemblyCapability:
    def create_assembly_work_order(
        self,
        materials: list[dict],
        procedure_id: int | None,
        procedure_name: str | None,
        quantity: int,
        worker_id: int | None,
        remark: str | None,
        actor_department: str,
    ) -> dict:
        self.require_capability(CAP_ASSEMBLY)
        return assembly.create_assembly_work_order(
            materials,
            procedure_id,
            procedure_name,
            quantity,
            worker_id,
            remark,
            actor_department,
        )
