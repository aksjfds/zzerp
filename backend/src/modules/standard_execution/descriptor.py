from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="standard_execution",
    public_api="modules.standard_execution.api",
    owns=(
        "procedure_price",
        "work_order_pay_detail",
    ),
    collaborates_with=(
        "engineering",
        "inventory",
        "production_core",
        "organization",
        "quality",
    ),
    collaboration_apis=(
        "modules.standard_execution.pay_reference_api",
        "modules.standard_execution.procedure_api",
        "modules.standard_execution.pricing_api",
        "modules.standard_execution.qc_api",
        "modules.standard_execution.reference_api",
    ),
)
