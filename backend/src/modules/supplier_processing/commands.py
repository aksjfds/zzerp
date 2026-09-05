"""Business use cases for supplier-processing work orders."""

from database import SessionLocal
from modules.errors import DomainError
from modules.planning.supplier_processing_api import (
    require_supplier_processing_task_for_creation,
)
from modules.production_core.operational_api import serialize_work_order
from modules.production_core.ownership_api import (
    cancel_supplier_processing_work_order_record,
    create_supplier_processing_work_order_record,
)


def create_supplier_processing_work_order(
    *,
    production_plan_item_id: int,
    supplier_flow_node_id: str,
    supplier_name: str,
    supplier_process_name: str,
    remark: str | None,
    actor_username: str,
) -> dict:
    supplier_name = _required_text(
        supplier_name,
        code="supplier_name_required",
        message="请填写供应商",
        max_length=200,
    )
    supplier_process_name = _required_text(
        supplier_process_name,
        code="supplier_process_name_required",
        message="请填写加工工艺",
        max_length=200,
    )
    remark = _optional_text(
        remark,
        max_length=1000,
        message="备注内容超过允许长度",
    )
    with SessionLocal.begin() as session:
        task = require_supplier_processing_task_for_creation(
            session,
            production_plan_item_id=production_plan_item_id,
            supplier_flow_node_id=supplier_flow_node_id,
        )
        if task.production_item_id is None:
            raise DomainError(
                "supplier_processing_material_missing",
                "委外加工任务缺少对应的生产物料",
                status_code=409,
            )
        order = create_supplier_processing_work_order_record(
            session,
            production_item_id=task.production_item_id,
            source_flow_node_id=task.source_flow_node_id,
            supplier_flow_node_id=task.supplier_flow_node_id,
            supplier_name=supplier_name,
            supplier_process_name=supplier_process_name,
            quantity=task.task_quantity,
            created_by=actor_username,
            remark=remark,
        )
        return serialize_work_order(session, order)


def _required_text(
    value: str,
    *,
    code: str,
    message: str,
    max_length: int,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainError(code, message, status_code=422)
    if len(normalized) > max_length:
        raise DomainError(
            f"{code}_too_long",
            "内容超过允许长度",
            status_code=422,
        )
    return normalized


def cancel_supplier_processing_work_order(
    *,
    work_order_id: int,
    actor_username: str,
) -> dict:
    if not actor_username.strip():
        raise DomainError("supplier_processing_actor_required", "取消操作人不能为空")
    with SessionLocal.begin() as session:
        order = cancel_supplier_processing_work_order_record(
            session,
            work_order_id=work_order_id,
        )
        return serialize_work_order(session, order)


def _optional_text(
    value: str | None,
    *,
    max_length: int,
    message: str,
) -> str | None:
    normalized = (value or "").strip()
    if len(normalized) > max_length:
        raise DomainError("remark_too_long", message, status_code=422)
    return normalized or None


__all__ = [
    "cancel_supplier_processing_work_order",
    "create_supplier_processing_work_order",
]
