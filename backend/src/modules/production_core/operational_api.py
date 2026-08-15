"""Public collaboration API for production operations.

Other business modules import production primitives from this facade instead
of depending on production_core implementation files.
"""

from modules.production_core.flow import (
    load_product_flow,
    load_production_flow,
    origin_route_procedure_ids,
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
    item_display,
    production_item_name,
    serialize_batch,
    serialize_work_order,
)
from modules.production_core.work_order_progress import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
    order_remaining_quantity,
    refresh_qc_work_order_closed,
    rework_pending_by_order,
    rework_pending_quantities,
)
from modules.production_core.work_order_support import (
    consume_repository,
    ensure_production_plan_active,
    mark_order_planned,
    move_to_node,
    node_context,
    production_item_unit_quantity,
    refresh_order_closed,
    target_department_id,
    terminal_unit_quantity,
)

__all__ = [
    "InventorySource",
    "calculate_assembly_output_progress",
    "calculate_work_order_progress",
    "capture_operation_state",
    "consume_order_source",
    "consume_repository",
    "ensure_production_plan_active",
    "create_order_record",
    "item_display",
    "load_product_flow",
    "load_production_flow",
    "mark_order_planned",
    "move_to_node",
    "node_context",
    "order_remaining_quantity",
    "origin_route_procedure_ids",
    "process_qc_node",
    "production_item_name",
    "production_item_unit_quantity",
    "record_movement",
    "record_undoable_operation",
    "refresh_order_closed",
    "refresh_qc_work_order_closed",
    "rework_pending_by_order",
    "rework_pending_quantities",
    "serialize_batch",
    "serialize_work_order",
    "target_department_id",
    "terminal_unit_quantity",
]
