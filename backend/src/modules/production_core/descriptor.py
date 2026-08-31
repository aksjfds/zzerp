from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="production_core",
    public_api="modules.production_core.api",
    owns=(
        "production_item",
        "repository",
        "production_movement",
        "production_operation_undo",
        "work_order",
        "work_order_material",
        "work_order_batch",
        "work_order_read_model",
    ),
    collaborates_with=(
        "engineering",
        "organization",
        "sales",
    ),
    collaboration_apis=(
        "modules.production_core.assembly_api",
        "modules.production_core.context_api",
        "modules.production_core.flow_api",
        "modules.production_core.inventory_api",
        "modules.production_core.model_api",
        "modules.production_core.operational_api",
        "modules.production_core.position_inventory_api",
        "modules.production_core.ownership_api",
        "modules.production_core.qc_api",
        "modules.production_core.qc_inventory_api",
        "modules.production_core.query_api",
        "modules.production_core.reference_api",
        "modules.production_core.transaction_api",
        "modules.production_core.workforce_api",
        "modules.production_core.workbench_read_api",
    ),
)
