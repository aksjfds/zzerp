from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="standard_execution",
    public_api="modules.standard_execution.api",
    owns=(
        "procedure_tag",
        "procedure_tag_set",
        "procedure_tag_price",
        "procedure_tag_stock",
        "tag_work_order_policy",
    ),
    collaborates_with=("engineering", "production_core", "organization", "quality"),
    collaboration_apis=(
        "modules.standard_execution.model_api",
        "modules.standard_execution.pay_reference_api",
        "modules.standard_execution.pricing_api",
        "modules.standard_execution.qc_api",
        "modules.standard_execution.tag_api",
    ),
)
