from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="standard_execution",
    public_api="modules.standard_execution.api",
    owns=(
        "procedure_price",
        "work_order_pay_detail",
    ),
    collaborates_with=("engineering", "production_core", "organization", "quality"),
    collaboration_apis=(
        "modules.standard_execution.model_api",
        "modules.standard_execution.pay_reference_api",
        "modules.standard_execution.pricing_api",
        "modules.standard_execution.qc_api",
    ),
)
