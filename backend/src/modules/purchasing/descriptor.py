from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="purchasing",
    public_api="modules.purchasing.api",
    owns=("purchase_receipt_execution_policy",),
    collaborates_with=(
        "production_core",
        "organization",
        "quality",
        "standard_execution",
    ),
    collaboration_apis=("modules.purchasing.qc_api",),
)
