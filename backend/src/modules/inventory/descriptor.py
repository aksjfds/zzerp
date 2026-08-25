from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="inventory",
    public_api="modules.inventory.api",
    owns=(
        "warehouse_stock",
        "warehouse_operation",
        "finished_inventory_stock",
        "finished_inventory_transaction",
        "finished_order_stock",
        "finished_goods_transaction",
    ),
    collaborates_with=("engineering", "organization", "production_core", "sales"),
    collaboration_apis=(
        "modules.inventory.identity_api",
        "modules.inventory.ownership_api",
        "modules.inventory.plan_stock_api",
        "modules.inventory.reference_api",
        "modules.inventory.finished_goods_api",
        "modules.inventory.warehouse_api",
    ),
)
