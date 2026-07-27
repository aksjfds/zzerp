from departments.contracts import CAP_PURCHASING
from modules.production_core import api as production


class PurchasingCapability:
    def create_source_work_order(
        self,
        repository_id: int | None,
        procedure_tag_stock_id: int | None,
        tag_names: list[str],
        quantity: int,
        worker_id: int | None,
        remark: str | None,
    ) -> dict:
        self.require_capability(CAP_PURCHASING)
        return production.create_work_order(
            repository_id,
            procedure_tag_stock_id,
            tag_names,
            quantity,
            worker_id,
            remark,
            self.descriptor.code,
        )
