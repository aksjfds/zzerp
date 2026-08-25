from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="sales",
    public_api="modules.sales.api",
    owns=("customer", "customer_order", "customer_order_item"),
    collaborates_with=(
    ),
    collaboration_apis=(
        "modules.sales.command_api",
        "modules.sales.context_api",
        "modules.sales.customer_api",
        "modules.sales.model_api",
        "modules.sales.reference_api",
        "modules.sales.transaction_api",
    ),
)
