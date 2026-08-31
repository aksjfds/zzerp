from typing import Literal, TypeAlias

from domain.production_types import WorkOrderStatus


CustomerOrderStatus: TypeAlias = Literal[
    "draft",
    "confirmed",
    "planned",
    "cancelled",
    "closed",
]
ProductionPlanStatus: TypeAlias = Literal["draft", "confirmed", "cancelled", "completed"]
ProductionItemType: TypeAlias = Literal["part", "assembly", "finished_product"]
FlowNodeType: TypeAlias = Literal[
    "part",
    "process",
    "qc",
    "finished_inbound",
    "assembly",
    "supplier_processing",
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
