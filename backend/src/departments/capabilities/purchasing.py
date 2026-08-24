from departments.contracts import CAP_PURCHASING
from departments.work_order_orchestration import create_work_order


class PurchasingCapability:
    def create_source_work_order(
        self,
        repository_id: int,
        procedure_id: int | None,
        procedure_name: str | None,
        quantity: int,
        worker_id: int | None,
        remark: str | None,
        actor_username: str,
    ) -> dict:
        self.require_capability(CAP_PURCHASING)
        return create_work_order(
            repository_id,
            procedure_id,
            procedure_name,
            quantity,
            worker_id,
            remark,
            actor_username,
            self.descriptor.code,
            False,
        )
