from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="planning",
    public_api="modules.planning.api",
    owns=(
        "production_plan",
        "production_plan_item",
        "production_route_task",
        "department_task_read_model",
        "order_production_read_model",
        "production_card_read_model",
        "production_progress_detail_read_model",
    ),
    collaborates_with=(
        "engineering",
        "inventory",
        "organization",
        "production_core",
        "sales",
        "workforce",
    ),
    collaboration_apis=(
        "modules.planning.execution_api",
        "modules.planning.execution_contract",
        "modules.planning.plan_api",
        "modules.planning.reference_api",
        "modules.planning.sales_api",
        "modules.planning.sales_progress_api",
    ),
)
