from zzerp.modules.engineering.contracts import ProcessFlowPayload
from zzerp.modules.engineering.routing import validate_nodes
from zzerp.time import business_iso


def serialize_bom(item):
    return {
        key: getattr(item, key)
        for key in ("id", "product_id", "part_name", "part_no", "pcs", "sort_order")
    } | {"remark": item.remark or ""}


def serialize_product_summary(
    product, bom_count, customer_name, *, design_ready, design_ready_reason
):
    return {
        key: getattr(product, key)
        for key in (
            "id",
            "revision",
            "customer_id",
            "product_name",
            "factory_code",
            "customer_code",
        )
    } | {
        "customer_name": customer_name,
        "bom_count": bom_count,
        "appearance_names": [appearance.appearance_name for appearance in product.appearances],
        "design_ready": design_ready,
        "design_ready_reason": design_ready_reason,
        "created_at": business_iso(product.created_at),
        "updated_at": business_iso(product.updated_at),
    }


def serialize_product_detail(
    session,
    product,
    empty_flow,
    appearance_id=None,
    *,
    customer_name,
    design_ready,
    design_ready_reason,
    base_info_editable,
    appearance_editable,
):
    appearance = next((a for a in product.appearances if a.id == appearance_id), None)
    if appearance_id is None and product.appearances:
        appearance = min(product.appearances, key=lambda a: a.id)
    record = next(
        (f for f in product.process_flows if appearance and f.appearance_id == appearance.id), None
    )
    payload = (
        record.draft_flow_json
        if record and record.draft_flow_json is not None
        else record.flow_json
        if record
        else empty_flow
    )
    flow = validate_nodes(session, product.id, ProcessFlowPayload.model_validate(payload))
    summary = serialize_product_summary(
        product,
        len(product.bom_items),
        customer_name,
        design_ready=design_ready,
        design_ready_reason=design_ready_reason,
    )
    summary.pop("bom_count")
    summary.pop("appearance_names")
    return summary | {
        "appearance_id": appearance.id if appearance else None,
        "appearance_name": appearance.appearance_name if appearance else "",
        "appearances": [
            {"id": a.id, "appearance_name": a.appearance_name}
            for a in sorted(product.appearances, key=lambda a: a.id)
        ],
        "base_info_editable": base_info_editable,
        "appearance_editable": appearance_editable,
        "bom_items": [serialize_bom(item) for item in product.bom_items],
        "process_flow": flow.model_dump(exclude_none=True),
        "process_flow_is_draft": bool(record and record.draft_flow_json is not None),
    }
