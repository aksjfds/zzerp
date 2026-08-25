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
FinishedInventoryTransactionType: TypeAlias = Literal[
    "receipt",
    "issue",
    "finished_receipt",
    "customer_shipment",
    "finished_stock_issue",
    "finished_surplus_transfer",
]
FinishedInventoryTransactionSourceType: TypeAlias = Literal[
    "finished_inventory_stock",
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
    "qc",
    "stamp",
    "warehouse",
]
