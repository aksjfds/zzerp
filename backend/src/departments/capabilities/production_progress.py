from departments.contracts import CAP_PRODUCTION_PROGRESS
from modules.planning import api as planning


class ProductionProgressCapability:
    def get_production_progress_item(
        self,
        production_plan_item_id: int,
        processing_workshop: str | None = None,
        flow_node_id: str | None = None,
    ) -> dict:
        self.require_capability(CAP_PRODUCTION_PROGRESS)
        return planning.get_department_production_progress_item(
            self.descriptor.code,
            production_plan_item_id,
            processing_workshop,
            flow_node_id,
        )

    def list_production_progress(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_PRODUCTION_PROGRESS)
        return planning.list_department_production_progress(
            self.descriptor.code,
            page,
            page_size,
            keyword,
        )
