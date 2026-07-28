from departments.contracts import CAP_PRODUCTION_PROGRESS
from modules.planning import api as planning


class ProductionProgressCapability:
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
