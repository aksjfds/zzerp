from departments.contracts import CAP_WORKERS
from modules.workforce import api as workforce


class WorkforceCapability:
    def list_workers(self) -> list[dict]:
        self.require_capability(CAP_WORKERS)
        return workforce.list_department_workers(self.descriptor.code)

    def worker_overview(self) -> dict:
        self.require_capability(CAP_WORKERS)
        return workforce.department_worker_overview(self.descriptor.code)

    def worker_history(self, worker_id: int, month: str) -> list[dict]:
        self.require_capability(CAP_WORKERS)
        return workforce.worker_history(worker_id, month, self.descriptor.code)

    def worker_pay_summary(self, worker_id: int, month: str) -> dict:
        self.require_capability(CAP_WORKERS)
        return workforce.worker_pay_summary(
            worker_id,
            month,
            self.descriptor.code,
        )

    def create_worker(
        self,
        worker_name: str,
        workshop_id: int | None,
    ) -> dict:
        self.require_capability(CAP_WORKERS)
        return workforce.create_department_worker(
            self.descriptor.code,
            worker_name,
            workshop_id,
        )
