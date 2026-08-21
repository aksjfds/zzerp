from departments.contracts import CAP_PURCHASING
from modules.production_core import api as production


class PurchasingCapability:
    def create_source_work_order(
        self,
        repository_id: int,
        procedure_id: int | None,
        procedure_name: str | None,
        quantity: int,
        worker_id: int | None,
        remark: str | None,
    ) -> dict:
        self.require_capability(CAP_PURCHASING)
        return production.create_work_order(
            repository_id,
            procedure_id,
            procedure_name,
            quantity,
            worker_id,
            remark,
            self.descriptor.code,
        )
