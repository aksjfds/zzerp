from __future__ import annotations

"""Assembly work-order completion and QC submission."""

from sqlalchemy import select

from domain.identity import can_access_department
from domain.production_types import COMPLETION_QC, WorkOrderCompletionAction
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.assembly_api import (
    load_production_item,
    load_repositories,
    record_assembly_output,
)
from modules.production_core.context_api import WorkOrderContext
from modules.production_core.model_api import WorkOrderMaterial
from modules.production_core.operational_api import (
    consume_repository,
    node_context,
    order_remaining_quantity,
    process_qc_node,
    record_movement,
    serialize_work_order,
    target_department_id,
)
from modules.production_core.ownership_api import (
    add_repository_quantity,
    assign_work_order_repository,
)
from modules.production_core.material_state_api import (
    QC_NONE,
    transition_work_order_material_state,
)
from modules.quality.submission_api import create_inspection_batch


def submit_assembly_work_order(
    session,
    order: WorkOrderContext,
    quantity: int,
    completion_action: WorkOrderCompletionAction,
    user_department: str | None,
    user_is_system: bool,
) -> dict:
    if not can_access_department(user_department, user_is_system, "assembly"):
        raise DomainError(
            "department_access_denied",
            "只有装配部可以操作装配工单",
            status_code=403,
        )
    remaining = order_remaining_quantity(order)
    if quantity != remaining:
        raise DomainError("assembly_submission_must_be_full", "装配工单必须整单提交")

    input_item = load_production_item(
        session,
        order.production_item_id,
        for_update=True,
    )
    context, assembly_node = node_context(session, input_item, order.flow_node_id)
    qc_node = process_qc_node(context.flow, context.nodes, assembly_node["id"])
    if completion_action == COMPLETION_QC and qc_node is None:
        raise DomainError("work_order_qc_not_configured", "装配节点后未配置QC节点")
    materials = session.scalars(
        select(WorkOrderMaterial)
        .where(WorkOrderMaterial.work_order_id == order.id)
        .order_by(WorkOrderMaterial.id)
    ).all()
    continuation = order.repository_id is not None
    output_item = input_item
    output_quantity = quantity * (
        1 if continuation else int(assembly_node.get("output_pcs", 1))
    )
    if continuation:
        repositories = load_repositories(
            session, {order.repository_id},
            for_update=True,
        )
        source = repositories[0] if repositories else None
        if source is None or source.quantity < quantity:
            raise DomainError("assembly_material_insufficient", "当前在制装配体数量不足")
        if (
            len(materials) != 1
            or materials[0].repository_id is not None
            or materials[0].production_item_id != source.production_item_id
            or materials[0].source_processing_state_id != source.processing_state_id
            or materials[0].quantity != quantity
            or materials[0].source_work_order_id != source.source_work_order_id
        ):
            raise DomainError(
                "assembly_continuation_snapshot_invalid",
                "装配后续工艺的投入来源快照不完整",
                status_code=409,
            )
        assign_work_order_repository(order, None)
        session.flush()
        consume_repository(session, source, quantity)
    if completion_action == COMPLETION_QC:
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        batch = create_inspection_batch(
            session,
            order=order,
            submitted_quantity=output_quantity,
            execution_flow_node_id=assembly_node["id"],
            expected_submission_quantity=output_quantity,
        )
        record_movement(
            session,
            production_item=output_item,
            quantity=output_quantity,
            movement_type="assembly_output",
            source_flow_node_id=assembly_node["id"],
            target_flow_node_id=qc_node["id"],
            source_department_id=target_department_id(session, assembly_node),
            target_department_id=qc_department_id,
            work_order=order,
            work_order_batch=batch,
        )
        record_assembly_output(
            order,
            completed_quantity=quantity,
            close_order=False,
        )
        session.flush()
        return serialize_work_order(session, order)

    assembly_department = target_department_id(session, assembly_node)
    processing_state = transition_work_order_material_state(
        session,
        production_item=output_item,
        context=context,
        order=order,
        completed_flow_node_id=assembly_node["id"],
        resume_flow_node_id=assembly_node["id"],
        qc_status=QC_NONE,
        reset_history=not continuation,
    )
    add_repository_quantity(
        session,
        production_item_id=output_item.id,
        processing_state_id=processing_state.id,
        flow_node_id=assembly_node["id"],
        source_flow_node_id=assembly_node["id"],
        department_id=assembly_department,
        quantity=output_quantity,
        source_work_order_id=order.id,
    )
    record_movement(
        session,
        production_item=output_item,
        quantity=output_quantity,
        movement_type="assembly_output",
        source_flow_node_id=assembly_node["id"],
        target_flow_node_id=assembly_node["id"],
        source_department_id=assembly_department,
        target_department_id=assembly_department,
        work_order=order,
    )
    # Persist the output while the assembly order is still open.
    session.flush()
    record_assembly_output(
        order,
        completed_quantity=quantity,
        close_order=order.completed_quantity + quantity >= order.quantity,
    )
    session.flush()
    return serialize_work_order(session, order)
