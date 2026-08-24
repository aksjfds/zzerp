from departments.contracts import CAP_QUALITY
from departments.qc_orchestration import inspect_qc_batch
from modules.quality import api as quality
from schemas.production import QcInspection


class QualityCapability:
    def list_qc_batches(
        self,
        page: int,
        page_size: int,
        production_item_id: int | None,
        history: bool,
        keyword: str | None,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_QUALITY)
        return quality.list_qc_batches(
            page,
            page_size,
            production_item_id,
            history,
            keyword,
        )

    def inspect_qc_batch(
        self,
        batch_id: int,
        payload: QcInspection,
        actor_department: str | None,
        actor_is_system: bool,
    ) -> dict:
        self.require_capability(CAP_QUALITY)
        return inspect_qc_batch(
            batch_id,
            payload,
            actor_department,
            actor_is_system,
        )
