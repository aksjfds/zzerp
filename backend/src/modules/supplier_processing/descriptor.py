from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="supplier_processing",
    public_api="modules.supplier_processing.api",
    owns=(),
    collaborates_with=(
        "inventory",
        "planning",
        "production_core",
        "quality",
        "workforce",
    ),
)
