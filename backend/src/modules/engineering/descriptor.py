from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="engineering",
    public_api="modules.engineering.api",
    owns=(
        "product",
        "product_version",
        "product_bom",
        "product_process_flow",
        "product_department_route",
        "product_route_component",
    ),
    collaborates_with=(
        "sales",
        "organization",
    ),
    collaboration_apis=(
        "modules.engineering.command_api",
        "modules.engineering.model_api",
        "modules.engineering.product_reference_api",
        "modules.engineering.route_api",
    ),
)
