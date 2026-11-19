from modules.contracts import ModuleDescriptor

MODULE = ModuleDescriptor(
    name="planning",
    public_api="modules.planning.api",
    owns=("warehouse_lot", "warehouse_pick", "warehouse_allocation", "qc_inspection", "qc_rework_ticket", "qc_rework_event", "plan_product_route", "production_plan", "production_plan_item", "department_work_order", "department_work_order_movement", "department_handoff_ticket", "department_movement_receipt_link"),
    collaborates_with=("engineering", "sales", "organization", "identity"),
    collaboration_apis=(),
)
