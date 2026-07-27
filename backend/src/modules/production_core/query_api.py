"""Public read API shared with workforce and quality modules."""

from modules.production_core.work_order_queries import (
    list_qc_batches,
)

__all__ = ["list_qc_batches"]
