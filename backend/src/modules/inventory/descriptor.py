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
        "finished_goods_transaction",
    ),
    collaborates_with=("engineering", "organization", "production_core", "sales"),
    collaboration_apis=(
        "modules.inventory.identity_api",
        "modules.inventory.model_api",
        "modules.inventory.ownership_api",
        "modules.inventory.reference_api",
        "modules.inventory.reservation_api",
        "modules.inventory.finished_goods_api",
    ),
)
