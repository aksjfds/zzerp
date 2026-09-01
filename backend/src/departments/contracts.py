from dataclasses import dataclass


CAP_WORKERS = "workers"
CAP_STANDARD_EXECUTION = "standard_execution"
CAP_ASSEMBLY = "assembly"
CAP_QUALITY = "quality"
CAP_SPECIAL_PRINTING = "special_printing"
CAP_PRODUCTION_PROGRESS = "production_progress"
CAP_PRODUCTION_WORKBENCH = "production_workbench"
CAP_INVENTORY = "inventory"
CAP_FINISHED_GOODS = "finished_goods"

CAPABILITY_METHODS = {
    CAP_WORKERS: (
        "list_workers",
        "worker_overview",
        "worker_history",
        "worker_pay_summary",
        "create_worker",
    ),
    CAP_STANDARD_EXECUTION: ("create_source_work_order",),
    CAP_ASSEMBLY: ("create_assembly_work_order",),
    CAP_QUALITY: (
        "get_qc_work_order_detail",
        "list_qc_inspection_batches",
        "inspect_qc_batch",
        "decide_qc_destination",
        "undo_qc_inspection",
    ),
    CAP_SPECIAL_PRINTING: ("printing_profile",),
    CAP_PRODUCTION_PROGRESS: ("list_production_progress",),
    CAP_PRODUCTION_WORKBENCH: ("list_production_workbench_positions",),
    CAP_INVENTORY: (),
    CAP_FINISHED_GOODS: (),
}


@dataclass(frozen=True)
class DepartmentDescriptor:
    code: str
    name: str
    execution_module: str
    capabilities: frozenset[str]

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities
