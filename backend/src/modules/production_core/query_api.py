"""Public read API shared with workforce and quality modules."""

from modules.production_core.work_order_queries import (
    get_qc_work_order_detail,
    list_qc_inspection_batches,
)

__all__ = ["get_qc_work_order_detail", "list_qc_inspection_batches"]
