"""Public collaboration API for production operations.

Other business modules import production primitives from this facade instead
of depending on production_core implementation files.
"""

from modules.production_core.flow import (
    load_product_flow,
    load_production_flow,
    process_qc_node,
)
from modules.production_core.movements import record_movement
from modules.production_core.operation_undo import (
    capture_operation_state,
    record_undoable_operation,
)
from modules.production_core.work_order_commands import (
    InventorySource,
    consume_order_source,
    create_order_record,
)
from modules.production_core.work_order_presenters import (
    ProductionItemDisplayContext,
    item_display,
    production_item_name,
    serialize_batch,
    serialize_work_order,
)
from modules.production_core.work_order_progress import (
    can_close_production_work_order,
    calculate_assembly_output_progress,
    calculate_work_order_progress,
    order_remaining_quantity,
    refresh_qc_work_order_closed,
    rework_pending_by_order,
    rework_pending_quantities,
)
from modules.production_core.work_order_support import (
    consume_repository,
    move_to_node,
    node_context,
    production_item_unit_quantity,
    shipping_node_and_unit_quantity,
    target_department_id,
    terminal_unit_quantity,
)

__all__ = [
    "InventorySource",
    "ProductionItemDisplayContext",
    "can_close_production_work_order",
    "calculate_assembly_output_progress",
    "calculate_work_order_progress",
    "capture_operation_state",
    "consume_order_source",
    "consume_repository",
    "create_order_record",
    "item_display",
    "load_product_flow",
    "load_production_flow",
    "move_to_node",
    "node_context",
    "order_remaining_quantity",
    "process_qc_node",
    "production_item_name",
    "production_item_unit_quantity",
    "record_movement",
    "record_undoable_operation",
    "refresh_qc_work_order_closed",
    "rework_pending_by_order",
    "rework_pending_quantities",
    "serialize_batch",
    "serialize_work_order",
    "shipping_node_and_unit_quantity",
    "target_department_id",
    "terminal_unit_quantity",
]
