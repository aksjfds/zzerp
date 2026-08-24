from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="organization",
    public_api="modules.organization.api",
    owns=("department", "workshop", "procedure"),
    collaboration_apis=(
        "modules.organization.context_api",
        "modules.organization.model_api",
        "modules.organization.read_api",
        "modules.organization.transaction_api",
    ),
)
