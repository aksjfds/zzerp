from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="planning",
    public_api="modules.planning.api",
    owns=(
        "production_plan",
        "production_plan_item",
        "pmc_part_progress_read_model",
        "production_reporting",
    ),
    collaborates_with=(
        "assembly",
        "engineering",
        "inventory",
        "organization",
        "production_core",
        "quality",
        "sales",
        "standard_execution",
    ),
    collaboration_apis=(
        "modules.planning.model_api",
        "modules.planning.plan_api",
    ),
)
