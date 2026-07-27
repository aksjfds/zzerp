from datetime import date

from departments.contracts import CAP_REPOSITORIES
from modules.production_core import api as production


class RepositoryCapability:
    def list_repositories(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
        arrived_from: date | None,
        arrived_to: date | None,
        work_status: str,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_REPOSITORIES)
        return production.list_production_cards(
            self.descriptor.code,
            page,
            page_size,
            keyword,
            arrived_from,
            arrived_to,
            work_status,
        )
