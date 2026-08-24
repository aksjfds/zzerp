from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="engineering",
    public_api="modules.engineering.api",
    owns=(
        "product",
        "product_version",
        "product_bom",
        "product_process_flow",
        "product_route_task",
    ),
    collaborates_with=(
        "organization",
        "sales",
    ),
    collaboration_apis=(
        "modules.engineering.command_api",
        "modules.engineering.model_api",
        "modules.engineering.pricing_api",
        "modules.engineering.product_reference_api",
    ),
)
