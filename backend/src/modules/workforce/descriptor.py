from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="workforce",
    public_api="modules.workforce.api",
    owns=("worker_management", "worker_history", "worker_pay_projection"),
    collaborates_with=(
        "engineering",
        "organization",
        "production_core",
        "quality",
        "standard_execution",
    ),
    collaboration_apis=(
        "modules.workforce.model_api",
        "modules.workforce.reference_api",
    ),
)
