from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="inventory",
    public_api="modules.inventory.api",
    owns=(
        "inventory_stock",
        "inventory_reservation",
        "inventory_receipt",
        "inventory_transaction",
        "finished_order_stock",
    ),
    collaborates_with=("engineering", "organization", "planning", "production_core", "sales"),
    collaboration_apis=(
        "modules.inventory.identity",
        "modules.inventory.model_api",
        "modules.inventory.ownership_api",
        "modules.inventory.reservation_api",
        "modules.inventory.finished_goods_api",
    ),
)
