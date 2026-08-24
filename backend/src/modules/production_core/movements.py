from domain.production_types import (
    WORK_ORDER_MOVEMENT_TYPES,
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_SUBMISSION_MOVEMENT_TYPES,
)
from modules.errors import DomainError
from modules.production_core.context_api import (
    InspectionBatchContext,
    WorkOrderContext,
)
from modules.production_core.persistence import ProductionItem, ProductionMovement


def record_movement(
    session,
    *,
    production_item: ProductionItem,
    quantity: int,
    movement_type: str,
    source_flow_node_id: str | None,
    target_flow_node_id: str | None,
    source_department_id: int | None = None,
    target_department_id: int | None = None,
    work_order: WorkOrderContext | None = None,
    work_order_batch: InspectionBatchContext | None = None,
    work_order_material_id: int | None = None,
) -> ProductionMovement | None:
    if quantity <= 0:
        return None
    _validate_work_order_movement(
        production_item=production_item,
        quantity=quantity,
        movement_type=movement_type,
        source_flow_node_id=source_flow_node_id,
        work_order=work_order,
        work_order_batch=work_order_batch,
    )
    movement = ProductionMovement(
        production_item_id=production_item.id,
        source_flow_node_id=source_flow_node_id,
        target_flow_node_id=target_flow_node_id,
        source_department_id=source_department_id,
        target_department_id=target_department_id,
        quantity=quantity,
        movement_type=movement_type,
        work_order_id=work_order.id if work_order is not None else None,
        work_order_batch_id=(
            work_order_batch.id if work_order_batch is not None else None
        ),
        work_order_material_id=work_order_material_id,
    )
    session.add(movement)
    return movement


def _validate_work_order_movement(
    *,
    production_item: ProductionItem,
    quantity: int,
    movement_type: str,
    source_flow_node_id: str | None,
    work_order: WorkOrderContext | None,
    work_order_batch: InspectionBatchContext | None,
) -> None:
    expected_order_type = WORK_ORDER_MOVEMENT_TYPES.get(movement_type)
    if expected_order_type is not None:
        if work_order is None or work_order.work_order_type != expected_order_type:
            raise DomainError(
                "production_movement_work_order_invalid",
                "生产流水与工单类型不一致",
            )
        if movement_type not in {"assembly_input", "assembly_input_restore"}:
            if production_item.id != work_order.production_item_id:
                raise DomainError(
                    "production_movement_item_invalid",
                    "生产流水与工单生产项不一致",
                )
        if (
            movement_type in WORK_ORDER_SUBMISSION_MOVEMENT_TYPES
            and work_order.status != WORK_ORDER_STATUS_OPEN
        ):
            raise DomainError("work_order_closed", "生产工单已经结单")
        if (
            movement_type in WORK_ORDER_SUBMISSION_MOVEMENT_TYPES
            and source_flow_node_id != work_order.flow_node_id
        ):
            raise DomainError(
                "production_movement_node_invalid",
                "生产流水与工单执行节点不一致",
            )
    elif work_order is not None and movement_type not in {
        "qc_qualified",
        "qc_rework",
        "scrap",
        "lost",
    }:
        raise DomainError(
            "production_movement_work_order_invalid",
            "当前流水类型不能关联工单",
        )

    if (
        work_order is not None
        and movement_type in {"qc_qualified", "qc_rework", "scrap", "lost"}
        and production_item.id != work_order.production_item_id
    ):
        raise DomainError(
            "production_movement_item_invalid",
            "QC流水与工单生产项不一致",
        )

    if work_order_batch is not None:
        if work_order is None or work_order_batch.work_order_id != work_order.id:
            raise DomainError(
                "production_movement_batch_invalid",
                "生产流水批次不属于当前工单",
            )
        if (
            movement_type in {"process", "purchase_receipt", "assembly_output"}
            and quantity != work_order_batch.submitted_quantity
        ):
            raise DomainError(
                "production_movement_batch_quantity_invalid",
                "提交流水数量与送检批次数量不一致",
            )
