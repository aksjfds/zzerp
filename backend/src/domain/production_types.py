from typing import Literal, TypeAlias


WORK_ORDER_STANDARD = "standard"
WORK_ORDER_ASSEMBLY = "assembly"
WORK_ORDER_SUPPLIER_PROCESSING = "supplier_processing"
WORK_ORDER_TYPES = frozenset({
    WORK_ORDER_STANDARD,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_SUPPLIER_PROCESSING,
})
STANDARD_EXECUTION_WORK_ORDER_TYPES = frozenset({
    WORK_ORDER_STANDARD,
    WORK_ORDER_ASSEMBLY,
})

WORK_ORDER_STATUS_OPEN = "open"
WORK_ORDER_STATUS_CLOSED = "closed"
WORK_ORDER_STATUS_CANCELLED = "cancelled"
WORK_ORDER_STATUSES = frozenset({
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_STATUS_CLOSED,
    WORK_ORDER_STATUS_CANCELLED,
})

COMPLETION_DIRECT = "direct"
COMPLETION_QC = "qc"

QC_DESTINATION_RETURN = "return"
QC_DESTINATION_RELEASE = "release"
QC_DESTINATION_INVENTORY = "inventory"

WorkOrderCompletionAction: TypeAlias = Literal["direct", "qc"]
WorkOrderType: TypeAlias = Literal[
    "standard",
    "assembly",
    "supplier_processing",
]
WorkOrderStatus: TypeAlias = Literal["open", "closed", "cancelled"]
QcQualifiedDestination: TypeAlias = Literal["return", "release", "inventory"]

QC_SUPPORTED_WORK_ORDER_TYPES = STANDARD_EXECUTION_WORK_ORDER_TYPES
REWORK_TRACKED_WORK_ORDER_TYPES = STANDARD_EXECUTION_WORK_ORDER_TYPES

WORK_ORDER_MOVEMENT_TYPES = {
    "process": WORK_ORDER_STANDARD,
    "assembly_input": WORK_ORDER_ASSEMBLY,
    "assembly_input_restore": WORK_ORDER_ASSEMBLY,
    "assembly_output": WORK_ORDER_ASSEMBLY,
}
WORK_ORDER_SUBMISSION_MOVEMENT_TYPES = frozenset({
    "process",
    "assembly_input",
    "assembly_output",
})
