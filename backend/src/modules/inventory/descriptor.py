from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="inventory",
    public_api="modules.inventory.api",
    owns=(
        "warehouse_stock",
        "warehouse_operation",
        "finished_receipt",
        "finished_stock",
        "finished_stock_reservation",
        "finished_stock_transaction",
    ),
    collaborates_with=("engineering", "organization", "production_core", "sales"),
    collaboration_apis=(
        "modules.inventory.identity_api",
        "modules.inventory.plan_stock_api",
        "modules.inventory.reference_api",
        "modules.inventory.finished_receipt_api",
        "modules.inventory.finished_shipment_api",
        "modules.inventory.finished_stock_query_api",
        "modules.inventory.warehouse_api",
    ),
)
