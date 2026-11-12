from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="planning",
    public_api="modules.planning.api",
    owns=("production_plan", "department_work_order", "department_work_order_movement"),
    collaborates_with=("engineering", "sales", "organization", "identity"),
    collaboration_apis=("modules.planning.reference_api",),
)
