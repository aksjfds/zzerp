from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="sales",
    public_api="modules.sales.api",
    owns=("customer",),
    collaboration_apis=("modules.sales.customer_api",),
)
