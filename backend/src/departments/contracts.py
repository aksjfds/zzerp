from dataclasses import dataclass


CAP_REPOSITORIES = "repositories"
CAP_WORK_ORDERS = "work_orders"
CAP_WORKERS = "workers"
CAP_STANDARD_EXECUTION = "standard_execution"
CAP_PURCHASING = "purchasing"
CAP_ASSEMBLY = "assembly"
CAP_QUALITY = "quality"
CAP_SPECIAL_PRINTING = "special_printing"
CAP_PRODUCTION_PROGRESS = "production_progress"

CAPABILITY_METHODS = {
    CAP_REPOSITORIES: ("list_repositories",),
    CAP_WORK_ORDERS: ("list_work_orders",),
    CAP_WORKERS: (
        "list_workers",
        "worker_overview",
        "worker_history",
        "worker_pay_summary",
        "create_worker",
    ),
    CAP_STANDARD_EXECUTION: ("list_tag_cards", "create_source_work_order"),
    CAP_PURCHASING: ("create_source_work_order",),
    CAP_ASSEMBLY: ("create_assembly_work_order",),
    CAP_QUALITY: ("list_qc_batches", "inspect_qc_batch", "dispatch_qc_batch"),
    CAP_SPECIAL_PRINTING: ("printing_profile",),
    CAP_PRODUCTION_PROGRESS: ("list_production_progress",),
}


@dataclass(frozen=True)
class DepartmentDescriptor:
    code: str
    name: str
    execution_module: str
    capabilities: frozenset[str]

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities
