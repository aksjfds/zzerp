from departments.contracts import CAP_QUALITY
from departments.qc_orchestration import (
    decide_qc_destination,
    inspect_qc_batch,
    undo_qc_inspection,
    undo_qc_destination,
)
from modules.quality import api as quality
from schemas.production import QcDestinationInput, QcInspection


class QualityCapability:
    def get_qc_work_order_detail(self, work_order_id: int) -> dict:
        self.require_capability(CAP_QUALITY)
        return quality.get_qc_work_order_detail(work_order_id)

    def list_qc_inspection_batches(
        self,
        page: int,
        page_size: int,
        history: bool,
        keyword: str | None,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_QUALITY)
        return quality.list_qc_inspection_batches(
            page,
            page_size,
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

    def decide_qc_destination(
        self,
        batch_id: int,
        payload: QcDestinationInput,
        actor_username: str,
        actor_department: str | None,
        actor_is_system: bool,
    ) -> dict:
        self.require_capability(CAP_QUALITY)
        return decide_qc_destination(
            batch_id,
            payload,
            actor_username,
            actor_department,
            actor_is_system,
        )

    def undo_qc_inspection(
        self,
        batch_id: int,
        actor_department: str | None,
        actor_is_system: bool,
    ) -> None:
        self.require_capability(CAP_QUALITY)
        undo_qc_inspection(batch_id, actor_department, actor_is_system)

    def undo_qc_destination(
        self,
        batch_id: int,
        actor_username: str,
        actor_department: str | None,
        actor_is_system: bool,
    ) -> dict:
        self.require_capability(CAP_QUALITY)
        return undo_qc_destination(
            batch_id,
            actor_username,
            actor_department,
            actor_is_system,
        )
