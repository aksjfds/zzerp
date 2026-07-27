from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="sales",
    public_api="modules.sales.api",
    owns=("customer", "customer_order", "customer_order_item"),
    collaborates_with=(
        "engineering",
        "organization",
        "production_core",
        "quality",
        "standard_execution",
    ),
    collaboration_apis=(
        "modules.sales.customer_api",
        "modules.sales.model_api",
        "modules.sales.reference_api",
    ),
)
