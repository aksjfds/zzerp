from typing import Literal, TypeAlias


CustomerOrderStatus: TypeAlias = Literal[
    "draft",
    "confirmed",
    "planned",
    "cancelled",
    "closed",
]
ProductionPlanStatus: TypeAlias = Literal["draft", "confirmed", "cancelled", "completed"]
ProductionItemType: TypeAlias = Literal["part", "assembly", "finished_product"]
FlowNodeType: TypeAlias = Literal["part", "process", "qc", "shipping", "assembly"]
WorkOrderStatus: TypeAlias = Literal["open", "closed", "cancelled"]
InventoryDepartmentCode: TypeAlias = Literal["warehouse", "finished"]
InventoryTransactionType: TypeAlias = Literal[
    "receipt",
    "reserve",
    "release",
    "issue",
    "adjust_in",
    "adjust_out",
    "finished_receipt",
    "customer_shipment",
    "finished_stock_issue",
    "finished_surplus_transfer",
]
InventoryTransactionSourceType: TypeAlias = Literal[
    "inventory_stock",
    "finished_order_stock",
]
UserDepartmentCode: TypeAlias = Literal[
    "assembly",
    "business",
    "cnc",
    "engineering",
    "finished",
    "outsource",
    "pmc",
    "polish",
    "purchasing",
    "qc",
    "stamp",
    "warehouse",
]
