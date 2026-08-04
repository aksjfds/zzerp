from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="quality",
    public_api="modules.quality.api",
    owns=("work_order_batch_inspection", "qc_dispatch"),
    collaborates_with=(
        "production_core",
        "standard_execution",
        "purchasing",
        "assembly",
        "organization",
        "workforce",
        "inventory",
    ),
    collaboration_apis=(
        "modules.quality.context_api",
        "modules.quality.inspection_api",
        "modules.quality.integration_api",
        "modules.quality.model_api",
        "modules.quality.ownership_api",
        "modules.quality.workforce_api",
    ),
)
