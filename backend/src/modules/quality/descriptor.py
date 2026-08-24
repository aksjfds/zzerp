from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="quality",
    public_api="modules.quality.api",
    owns=("work_order_batch_inspection_policy",),
    collaborates_with=(
        "organization",
        "production_core",
    ),
    collaboration_apis=(
        "modules.quality.command_api",
        "modules.quality.inspection_api",
        "modules.quality.submission_api",
        "modules.quality.routing_contract",
        "modules.quality.workforce_api",
    ),
)
