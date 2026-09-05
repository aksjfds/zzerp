"""Authoritative immutable processing states for production material."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modules.errors import DomainError
from modules.production_core.context_api import ProductionItemContext, WorkOrderContext
from modules.production_core.flow_api import ProductionFlowContext
from modules.production_core.persistence import MaterialProcessingState


QC_NONE = "none"
QC_RETURNED = "returned"
QC_RELEASED = "released"
QC_STORED = "stored"


@dataclass(frozen=True, slots=True)
class MaterialStateView:
    id: int
    product_id: int
    product_version: int
    item_type: str
    product_bom_id: int | None
    origin_flow_node_id: str
    display_text: str
    completed_flow_node_id: str
    resume_flow_node_id: str
    procedure_history: tuple[dict, ...]
    qc_status: str


def ensure_initial_material_state(
    session,
    production_item: ProductionItemContext,
    context: ProductionFlowContext,
    resume_flow_node_id: str,
) -> MaterialStateView:
    return _get_or_create_state(
        session,
        production_item=production_item,
        context=context,
        completed_flow_node_id=production_item.origin_flow_node_id,
        resume_flow_node_id=resume_flow_node_id,
        procedure_history=(),
        qc_status=QC_NONE,
    )


def transition_work_order_material_state(
    session,
    *,
    production_item: ProductionItemContext,
    context: ProductionFlowContext,
    order: WorkOrderContext,
    completed_flow_node_id: str,
    resume_flow_node_id: str,
    qc_status: str,
    reset_history: bool = False,
) -> MaterialStateView:
    source = (
        session.get(MaterialProcessingState, order.source_processing_state_id)
        if order.source_processing_state_id is not None and not reset_history
        else None
    )
    history = list(source.procedure_history) if source is not None else []
    procedure_name = (
        order.supplier_process_name
        if order.work_order_type == "supplier_processing"
        else order.work_order_name
    )
    normalized_name = str(procedure_name or "").strip()
    if not normalized_name:
        raise DomainError("material_state_procedure_missing", "工单缺少可记录的加工工艺")
    history.append({
        "flow_node_id": completed_flow_node_id,
        "procedure_id": order.procedure_id,
        "procedure_name": normalized_name,
        "is_temporary": bool(order.is_temporary),
        "completion_result": qc_status,
    })
    return _get_or_create_state(
        session,
        production_item=production_item,
        context=context,
        completed_flow_node_id=completed_flow_node_id,
        resume_flow_node_id=resume_flow_node_id,
        procedure_history=tuple(history),
        qc_status=qc_status,
    )


def get_material_state(session, state_id: int) -> MaterialStateView:
    state = session.get(MaterialProcessingState, state_id)
    if state is None:
        raise DomainError("material_processing_state_missing", "物料加工状态不存在", status_code=409)
    return _view(state)


def validate_material_state_identity(
    state: MaterialStateView,
    production_item: ProductionItemContext,
) -> None:
    expected_type = "part" if production_item.product_bom_id is not None else "assembly"
    if (
        state.product_id != production_item.product_id
        or state.product_version != production_item.product_version
        or state.item_type != expected_type
        or state.product_bom_id != production_item.product_bom_id
        or state.origin_flow_node_id != production_item.origin_flow_node_id
    ):
        raise DomainError(
            "material_processing_state_context_invalid",
            "加工状态与生产物料身份不一致",
            status_code=409,
        )


def find_material_states(
    session,
    *,
    product_id: int,
    product_version: int,
    product_bom_id: int | None,
    origin_flow_node_id: str,
) -> tuple[MaterialStateView, ...]:
    conditions = [
        MaterialProcessingState.product_id == product_id,
        MaterialProcessingState.product_version == product_version,
        MaterialProcessingState.origin_flow_node_id == origin_flow_node_id,
    ]
    if product_bom_id is None:
        conditions.append(MaterialProcessingState.product_bom_id.is_(None))
    else:
        conditions.append(MaterialProcessingState.product_bom_id == product_bom_id)
    return tuple(
        _view(state)
        for state in session.scalars(
            select(MaterialProcessingState)
            .where(*conditions)
            .order_by(MaterialProcessingState.id)
        )
    )


def _get_or_create_state(
    session,
    *,
    production_item: ProductionItemContext,
    context: ProductionFlowContext,
    completed_flow_node_id: str,
    resume_flow_node_id: str,
    procedure_history: tuple[dict, ...],
    qc_status: str,
) -> MaterialStateView:
    if qc_status not in {QC_NONE, QC_RETURNED, QC_RELEASED, QC_STORED}:
        raise DomainError("material_processing_state_qc_invalid", "物料质检状态无效")
    completed_node = context.nodes.get(completed_flow_node_id)
    resume_node = context.nodes.get(resume_flow_node_id)
    if completed_node is None or resume_node is None:
        raise DomainError("material_processing_state_node_missing", "物料加工状态引用的流程节点不存在")
    item_type = "part" if production_item.product_bom_id is not None else "assembly"
    canonical = {
        "product_id": production_item.product_id,
        "product_version": production_item.product_version,
        "item_type": item_type,
        "product_bom_id": production_item.product_bom_id,
        "origin_flow_node_id": production_item.origin_flow_node_id,
        "completed_flow_node_id": completed_flow_node_id,
        "resume_flow_node_id": resume_flow_node_id,
        "procedure_history": list(procedure_history),
        "qc_status": qc_status,
    }
    signature = sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    display_text = _display_text(
        context,
        procedure_history,
        completed_flow_node_id,
        resume_flow_node_id,
    )
    state_id = session.scalar(
        insert(MaterialProcessingState)
        .values(
            **canonical,
            display_text=display_text,
            state_signature=signature,
        )
        .on_conflict_do_nothing(index_elements=[MaterialProcessingState.state_signature])
        .returning(MaterialProcessingState.id)
    )
    state = (
        session.get(MaterialProcessingState, state_id)
        if state_id is not None
        else session.scalar(
            select(MaterialProcessingState).where(
                MaterialProcessingState.state_signature == signature
            )
        )
    )
    if state is None:
        raise DomainError("material_processing_state_create_failed", "物料加工状态创建失败")
    return _view(state)


def _display_text(
    context: ProductionFlowContext,
    history: tuple[dict, ...],
    completed_flow_node_id: str,
    resume_flow_node_id: str,
) -> str:
    resume_label = _node_label(context, resume_flow_node_id)
    if not history:
        return f"未加工 · 待{resume_label}"
    history_text = " → ".join(
        f"{_procedure_label(item)}（{_node_label(context, item['flow_node_id'])}，"
        f"{_completion_result_label(item.get('completion_result', QC_NONE))}）"
        for item in history
    )
    location_text = (
        f"留在{resume_label}"
        if resume_flow_node_id == completed_flow_node_id
        else f"待{resume_label}"
    )
    return f"{history_text} · {location_text}"


def _procedure_label(history_item: dict) -> str:
    name = str(history_item.get("procedure_name") or "").strip()
    return f"临时·{name}" if history_item.get("is_temporary") else name


def _completion_result_label(result: str) -> str:
    return {
        QC_NONE: "已完成",
        QC_RETURNED: "QC合格·送回",
        QC_RELEASED: "QC合格·放行",
        QC_STORED: "QC合格·入仓",
    }.get(result, "状态异常")


def _node_label(context: ProductionFlowContext, node_id: str) -> str:
    node = context.nodes.get(node_id, {})
    return str(node.get("label") or node.get("output_name") or node_id).strip()


def _view(state: MaterialProcessingState) -> MaterialStateView:
    return MaterialStateView(
        id=state.id,
        product_id=state.product_id,
        product_version=state.product_version,
        item_type=state.item_type,
        product_bom_id=state.product_bom_id,
        origin_flow_node_id=state.origin_flow_node_id,
        display_text=state.display_text,
        completed_flow_node_id=state.completed_flow_node_id,
        resume_flow_node_id=state.resume_flow_node_id,
        procedure_history=tuple(state.procedure_history or ()),
        qc_status=state.qc_status,
    )


__all__ = [
    "MaterialStateView",
    "QC_NONE",
    "QC_RELEASED",
    "QC_RETURNED",
    "QC_STORED",
    "ensure_initial_material_state",
    "find_material_states",
    "get_material_state",
    "transition_work_order_material_state",
    "validate_material_state_identity",
]
