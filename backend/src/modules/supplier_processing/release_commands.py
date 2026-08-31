"""QC release workflow for supplier-processing batches."""

from database import SessionLocal
from domain.identity import can_access_department
from modules.errors import DomainError
from modules.inventory.finished_receipt_api import register_pending_finished_receipt
from modules.production_core.operational_api import move_to_node
from modules.quality.supplier_processing_api import (
    finalize_supplier_processing_release,
    prepare_supplier_processing_release,
)


def release_supplier_processing_batch(
    *,
    batch_id: int,
    actor_username: str,
    actor_department: str | None,
    actor_is_system: bool,
) -> dict:
    if not can_access_department(actor_department, actor_is_system, "qc"):
        raise DomainError(
            "qc_access_denied",
            "只有 QC 可以放行委外加工合格品",
            status_code=403,
        )
    actor = actor_username.strip()
    if not actor:
        raise DomainError(
            "supplier_processing_release_actor_invalid",
            "放行操作人不能为空",
            status_code=422,
        )

    with SessionLocal.begin() as session:
        prepared = prepare_supplier_processing_release(session, batch_id)
        quantity = prepared.batch.qualified_quantity or 0
        target_department_id = move_to_node(
            session,
            prepared.production_item,
            prepared.target_node,
            quantity,
            prepared.qc_flow_node_id,
            source_work_order_id=prepared.order.id,
        )
        if target_department_id is None:
            raise DomainError(
                "supplier_processing_release_target_missing",
                "委外加工 QC 没有可放行的后续流程节点",
                status_code=409,
            )
        if prepared.target_node.get("type") == "finished_inbound":
            register_pending_finished_receipt(
                session,
                work_order_batch_id=prepared.batch.id,
                product_id=prepared.production_item.product_id,
                product_version=prepared.production_item.product_version,
                inbound_node_id=prepared.target_node["id"],
                released_quantity=quantity,
            )
        return finalize_supplier_processing_release(
            prepared,
            target_department_id=target_department_id,
            actor_username=actor,
        )


__all__ = ["release_supplier_processing_batch"]
