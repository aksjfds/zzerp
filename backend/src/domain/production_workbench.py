from typing import Literal, get_args


ProductionWorkbenchAttention = Literal[
    "all",
    "available",
    "processing",
    "ready_for_result",
    "qc",
    "rework",
]
ProductionWorkbenchPositionType = Literal["standard", "assembly"]

PRODUCTION_WORKBENCH_ATTENTION_FILTERS = frozenset(
    get_args(ProductionWorkbenchAttention)
)


__all__ = [
    "PRODUCTION_WORKBENCH_ATTENTION_FILTERS",
    "ProductionWorkbenchAttention",
    "ProductionWorkbenchPositionType",
]
