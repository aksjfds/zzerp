from __future__ import annotations

"""Restore materials consumed by a cancelled assembly work order."""

from sqlalchemy import select

from modules.errors import DomainError
from modules.production_core.assembly_api import load_production_item
from modules.production_core.context_api import WorkOrderContext
from modules.production_core.model_api import WorkOrderMaterial
from modules.production_core.operational_api import record_movement
from modules.production_core.ownership_api import (
    add_repository_quantity,
    assign_work_order_material_repository,
)


def restore_cancelled_assembly_materials(session, order: WorkOrderContext) -> None:
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .with_for_update()
    ).all()
    if order.repository_id is not None:
        if (
            len(materials) != 1
            or materials[0].repository_id is not None
            or materials[0].quantity != order.quantity
        ):
            raise DomainError(
                "assembly_continuation_snapshot_invalid",
                "装配后续工艺的投入来源快照不完整",
                status_code=409,
            )
        return
    for material in materials:
        production_item = load_production_item(
            session,
            material.production_item_id,
            for_update=True,
        )
        if production_item is None:
            raise DomainError("assembly_material_missing", "装配工单原配件不存在")
        repository = add_repository_quantity(
            session,
            production_item_id=material.production_item_id,
            processing_state_id=material.source_processing_state_id,
            flow_node_id=material.source_flow_node_id,
            source_flow_node_id=material.source_previous_flow_node_id,
            department_id=material.source_department_id,
            quantity=material.quantity,
            source_work_order_id=material.source_work_order_id,
        )
        assign_work_order_material_repository(
            material,
            repository.id if repository else None,
        )
        record_movement(
            session,
            production_item=production_item,
            quantity=material.quantity,
            movement_type="assembly_input_restore",
            source_flow_node_id=material.source_flow_node_id,
            target_flow_node_id=material.source_flow_node_id,
            source_department_id=material.source_department_id,
            target_department_id=material.source_department_id,
            work_order=order,
            work_order_material_id=material.id,
        )
