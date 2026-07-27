from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="engineering",
    public_api="modules.engineering.api",
    owns=("product", "product_version", "product_bom", "product_process_flow"),
    collaborates_with=(
        "organization",
        "production_core",
        "sales",
        "standard_execution",
    ),
    collaboration_apis=(
        "modules.engineering.model_api",
        "modules.engineering.pricing_api",
        "modules.engineering.product_reference_api",
    ),
)
