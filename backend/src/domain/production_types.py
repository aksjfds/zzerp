from typing import Literal, TypeAlias


WORK_ORDER_STANDARD = "standard"
WORK_ORDER_PURCHASE_RECEIPT = "purchase_receipt"
WORK_ORDER_ASSEMBLY = "assembly"
WORK_ORDER_TYPES = frozenset({
    WORK_ORDER_STANDARD,
    WORK_ORDER_PURCHASE_RECEIPT,
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

WorkOrderCompletionAction: TypeAlias = Literal["direct", "qc"]
QcQualifiedDisposition: TypeAlias = Literal["return", "release"]

QC_SUPPORTED_WORK_ORDER_TYPES = WORK_ORDER_TYPES
REWORK_TRACKED_WORK_ORDER_TYPES = frozenset({
    WORK_ORDER_STANDARD,
    WORK_ORDER_ASSEMBLY,
})

WORK_ORDER_MOVEMENT_TYPES = {
    "process": WORK_ORDER_STANDARD,
    "purchase_receipt": WORK_ORDER_PURCHASE_RECEIPT,
    "assembly_input": WORK_ORDER_ASSEMBLY,
    "assembly_input_restore": WORK_ORDER_ASSEMBLY,
    "assembly_output": WORK_ORDER_ASSEMBLY,
}
WORK_ORDER_SUBMISSION_MOVEMENT_TYPES = frozenset({
    "process",
    "purchase_receipt",
    "assembly_input",
    "assembly_output",
})
