"""Production-plan application commands and read models."""

from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import SessionLocal
from domain.time import business_iso, utc_now
from modules.errors import DomainError
from modules.engineering.model_api import ProductProcessFlow
from modules.inventory.reservation_api import (
    plan_item_stocks,
    release_plan_reservations,
    reserve_plan_item,
)
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_builder import (
    planned_finished_quantity,
    planned_product_quantity,
    refresh_plan_availability,
)
from modules.production_core.api import (
    cancel_order_production,
    initialize_order_production,
)
from modules.inventory.persistence import InventoryReservation


def get_order_plan(order_id: int) -> dict:
    with SessionLocal() as session:
        plan = _load_plan(session, order_id)
        if plan is None:
            raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
        if plan.status == "draft":
            refresh_plan_availability(session, plan)
        return serialize_plan(session, plan)


def update_order_plan(
    order_id: int,
    expected_revision: int,
    quantities: dict[int, int],
) -> dict:
    with SessionLocal.begin() as session:
        plan = _load_plan(session, order_id, for_update=True)
        if plan is None:
            raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
        if plan.status != "draft":
            raise DomainError("production_plan_not_editable", "只有未确认生产计划允许修改")
        _ensure_revision(plan, expected_revision)
        refresh_plan_availability(session, plan)
        editable_items = [item for item in plan.items if item.item_type == "part"]
        expected_ids = {item.id for item in editable_items}
        if set(quantities) != expected_ids:
            raise DomainError(
                "production_plan_items_incomplete",
                "必须提交生产计划中的全部普通配件",
                path="items",
            )
        for item in editable_items:
            quantity = quantities[item.id]
            item.planned_production_quantity = quantity
        _validate_product_output(session, plan.items)
        plan.revision += 1
        plan.updated_at = utc_now()
        session.flush()
        return serialize_plan(session, plan)


def confirm_order_plan(
    session: Session,
    order,
    *,
    expected_revision: int,
    actor_username: str,
) -> ProductionPlan:
    plan = _load_plan(session, order.id, for_update=True)
    if plan is None:
        raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
    if plan.status != "draft":
        raise DomainError("production_plan_not_confirmable", "当前生产计划不能确认")
    _ensure_revision(plan, expected_revision)
    refresh_plan_availability(session, plan)
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in plan.items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    for items in groups.values():
        finished = next(item for item in items if item.item_type == "finished_product")
        supported_quantity = planned_finished_quantity(session, items)
        if supported_quantity < finished.gross_required_quantity:
            raise DomainError(
                "planned_quantity_insufficient",
                f"{finished.item_code} {finished.item_name}按 BOM 最多可满足 "
                f"{supported_quantity} 件，少于订单需求 {finished.gross_required_quantity} 件",
                path="items",
            )
        _reserve_and_validate_plan_item(session, plan, finished, actor_username)
        for item in items:
            if item.item_type != "finished_product":
                item.gross_required_quantity = 0
                item.estimated_inventory_quantity = 0
                item.net_required_quantity = 0
                item.reserved_inventory_quantity = 0
        _reserve_flow_items(
            session,
            plan,
            items,
            finished.flow_node_id,
            finished.net_required_quantity,
            actor_username,
        )
    part_quantities = {
        (item.customer_order_item_id, item.product_bom_id, item.flow_node_id):
            item.planned_production_quantity
        for item in plan.items
        if item.item_type == "part" and item.product_bom_id is not None
    }
    initialize_order_production(session, order, part_quantities=part_quantities)
    plan.status = "confirmed"
    plan.confirmed_at = utc_now()
    plan.confirmed_by = actor_username
    plan.updated_at = utc_now()
    plan.revision += 1
    return plan


def cancel_order_plan(session: Session, order, actor_username: str) -> None:
    plan = _load_plan(session, order.id, for_update=True)
    if plan is None:
        return
    if plan.status == "cancelled":
        return
    release_plan_reservations(session, plan.id, actor_username)
    if order.status != "draft":
        cancel_order_production(session, order)
    plan.status = "cancelled"
    plan.updated_at = utc_now()
    plan.revision += 1


def serialize_plan(session: Session, plan: ProductionPlan) -> dict:
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in plan.items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    return {
        "id": plan.id,
        "customer_order_id": plan.customer_order_id,
        "status": plan.status,
        "revision": plan.revision,
        "product_summaries": [
            {
                "customer_order_item_id": customer_order_item_id,
                "product_id": finished.product_id,
                "product_version": finished.product_version,
                "product_code": finished.item_code,
                "product_name": finished.item_name,
                "order_quantity": finished.gross_required_quantity,
                "planned_finished_quantity": planned_product_quantity(items),
            }
            for customer_order_item_id, items in groups.items()
            for finished in [next(item for item in items if item.item_type == "finished_product")]
        ],
        "items": [
            {
                "id": item.id,
                "customer_order_item_id": item.customer_order_item_id,
                "item_type": item.item_type,
                "product_id": item.product_id,
                "product_version": item.product_version,
                "product_bom_id": item.product_bom_id,
                "flow_node_id": item.flow_node_id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "unit_requirement": item.unit_requirement,
                "gross_required_quantity": item.gross_required_quantity,
                "estimated_inventory_quantity": item.estimated_inventory_quantity,
                "net_required_quantity": item.net_required_quantity,
                "planned_production_quantity": item.planned_production_quantity,
                "reserved_inventory_quantity": item.reserved_inventory_quantity,
                "issued_inventory_quantity": item.issued_inventory_quantity,
                "available_inventory_quantity": max(
                    item.estimated_inventory_quantity - item.reserved_inventory_quantity,
                    0,
                ) if plan.status != "draft" else item.estimated_inventory_quantity,
            }
            for item in plan.items
            if item.item_type == "part"
        ],
        "inventory_items": _serialize_inventory_items(session, plan),
        "confirmed_at": business_iso(plan.confirmed_at),
        "confirmed_by": plan.confirmed_by,
        "created_at": business_iso(plan.created_at),
        "updated_at": business_iso(plan.updated_at),
    }


def _serialize_inventory_items(session: Session, plan: ProductionPlan) -> list[dict]:
    from modules.production_core.flow import completed_node_display_label, load_product_flow
    from modules.engineering.model_api import ProductBom

    stock_groups = plan_item_stocks(session, plan.items)
    bom_ids = {
        item.product_bom_id
        for item in plan.items
        if item.product_bom_id is not None
    }
    bom_by_id = {
        item.id: item
        for item in session.scalars(select(ProductBom).where(ProductBom.id.in_(bom_ids)))
    } if bom_ids else {}
    requirements = {
        item.product_bom_id: item.unit_requirement
        for item in plan.items
        if item.item_type == "part" and item.product_bom_id is not None
    }
    incoming_by_product: dict[tuple[int, int], dict[str, list[str]]] = {}
    reachable_bom_cache: dict[tuple[int, int, str], set[int]] = {}
    reservations = list(session.scalars(select(InventoryReservation).where(
        InventoryReservation.production_plan_id == plan.id
    )))
    reservation_totals: dict[tuple[int, int], tuple[int, int]] = {}
    for reservation in reservations:
        key = (reservation.production_plan_item_id, reservation.inventory_stock_id)
        reserved, issued = reservation_totals.get(key, (0, 0))
        reservation_totals[key] = (
            reserved + reservation.reserved_quantity,
            issued + reservation.issued_quantity,
        )
    rows: list[dict] = []
    seen_part_keys: set[tuple[int, int]] = set()
    for item in plan.items:
        if item.item_type == "part" and item.product_bom_id is not None:
            part_key = (item.customer_order_item_id, item.product_bom_id)
            if part_key in seen_part_keys:
                continue
            seen_part_keys.add(part_key)
        _flow, nodes = load_product_flow(session, item.product_id, item.product_version)
        product_key = (item.product_id, item.product_version)
        if product_key not in incoming_by_product:
            incoming: dict[str, list[str]] = {}
            for edge in _flow.get("edges", []):
                source_id = edge.get("source_node_id")
                target_id = edge.get("target_node_id")
                if source_id and target_id:
                    incoming.setdefault(target_id, []).append(source_id)
            incoming_by_product[product_key] = incoming
        stocks = stock_groups.get(item.identity_key, [])
        item_name = item.item_name
        if item.item_type == "part" and item.product_bom_id is not None:
            bom_item = bom_by_id.get(item.product_bom_id)
            if bom_item is not None:
                item_name = bom_item.part_name
        if not stocks:
            rows.append(_inventory_item_row(
                item,
                None,
                "—",
                0,
                0,
                0,
                item_name,
                _inventory_decomposition(
                    item,
                    0,
                    nodes,
                    incoming_by_product[product_key],
                    requirements,
                    bom_by_id,
                    reachable_bom_cache,
                ),
            ))
            continue
        for stock in stocks:
            reserved, issued = reservation_totals.get((item.id, stock.id), (0, 0))
            rows.append(_inventory_item_row(
                item,
                stock.id,
                completed_node_display_label(
                    _flow,
                    nodes,
                    stock.flow_node_id,
                    stock.completed_flow_node_id,
                ),
                max(stock.quantity - stock.reserved_quantity, 0),
                reserved,
                issued,
                item_name,
                _inventory_decomposition(
                    item,
                    max(stock.quantity - stock.reserved_quantity, 0),
                    nodes,
                    incoming_by_product[product_key],
                    requirements,
                    bom_by_id,
                    reachable_bom_cache,
                ),
            ))
    return rows


def _inventory_item_row(
    item: ProductionPlanItem,
    stock_id: int | None,
    completed_node_label: str,
    available: int,
    reserved: int,
    issued: int,
    item_name: str | None = None,
    decomposition: dict | None = None,
) -> dict:
    return {
        "id": stock_id or -item.id,
        "customer_order_item_id": item.customer_order_item_id,
        "item_type": item.item_type,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "product_bom_id": item.product_bom_id,
        "flow_node_id": item.flow_node_id,
        "item_code": item.item_code,
        "item_name": item_name or item.item_name,
        "completed_node_label": completed_node_label,
        "current_inventory_quantity": available,
        "reserved_inventory_quantity": reserved,
        "issued_inventory_quantity": issued,
        "decomposition": decomposition or {
            "finished_equivalent_quantity": 0,
            "parts": [],
        },
    }


def _inventory_decomposition(
    item: ProductionPlanItem,
    quantity: int,
    nodes: dict[str, dict],
    incoming: dict[str, list[str]],
    requirements: dict[int, int],
    bom_by_id: dict,
    reachable_bom_cache: dict[tuple[int, int, str], set[int]],
) -> dict:
    finished_equivalent = quantity if item.item_type == "finished_product" else (
        quantity // max(item.unit_requirement, 1)
    )
    if item.item_type == "finished_product":
        reachable_bom_ids: set[int] = set()
    elif item.item_type == "part":
        reachable_bom_ids = {item.product_bom_id} if item.product_bom_id is not None else set()
    else:
        cache_key = (item.product_id, item.product_version, item.flow_node_id)
        if cache_key not in reachable_bom_cache:
            reachable_bom_ids: set[int] = set()
            pending = list(incoming.get(item.flow_node_id, []))
            visited: set[str] = set()
            while pending:
                node_id = pending.pop()
                if node_id in visited:
                    continue
                visited.add(node_id)
                node = nodes.get(node_id, {})
                if node.get("type") == "part" and isinstance(node.get("bom_item_id"), int):
                    reachable_bom_ids.add(node["bom_item_id"])
                    continue
                pending.extend(incoming.get(node_id, []))
            reachable_bom_cache[cache_key] = reachable_bom_ids
        reachable_bom_ids = reachable_bom_cache[cache_key]
    parts = []
    for bom_id in sorted(
        reachable_bom_ids,
        key=lambda value: getattr(bom_by_id.get(value), "sort_order", 0),
    ):
        bom = bom_by_id.get(bom_id)
        if bom is None:
            continue
        equivalent_quantity = (
            quantity
            if item.item_type == "part" and item.product_bom_id == bom_id
            else finished_equivalent * requirements.get(bom_id, bom.pcs)
        )
        parts.append({
            "product_bom_id": bom.id,
            "item_code": bom.part_no,
            "item_name": bom.part_name,
            "quantity": equivalent_quantity,
        })
    return {
        "finished_equivalent_quantity": finished_equivalent,
        "parts": parts,
    }


def _validate_product_output(session: Session, items: list[ProductionPlanItem]) -> None:
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    for group in groups.values():
        finished = next(item for item in group if item.item_type == "finished_product")
        supported_quantity = planned_finished_quantity(session, group)
        if supported_quantity < finished.gross_required_quantity:
            raise DomainError(
                "planned_quantity_insufficient",
                f"{finished.item_code} {finished.item_name}按 BOM 最多可满足 "
                f"{supported_quantity} 件，少于订单需求 {finished.gross_required_quantity} 件",
                path="items",
            )


def _load_plan(
    session: Session,
    order_id: int,
    *,
    for_update: bool = False,
) -> ProductionPlan | None:
    statement = (
        select(ProductionPlan)
        .options(selectinload(ProductionPlan.items))
        .where(ProductionPlan.customer_order_id == order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _ensure_revision(plan: ProductionPlan, expected_revision: int) -> None:
    if plan.revision != expected_revision:
        raise DomainError(
            "production_plan_revision_conflict",
            "生产计划已发生变化，请重新加载",
            status_code=409,
        )


def _reserve_and_validate_plan_item(
    session: Session,
    plan: ProductionPlan,
    item: ProductionPlanItem,
    actor_username: str,
) -> None:
    allocated = reserve_plan_item(
        session,
        production_plan_id=plan.id,
        production_plan_item_id=item.id,
        plan_item=item,
        requested_quantity=item.gross_required_quantity,
        actor_username=actor_username,
    )
    item.reserved_inventory_quantity = allocated
    item.estimated_inventory_quantity = allocated
    item.net_required_quantity = item.gross_required_quantity - allocated
    if item.planned_production_quantity < item.net_required_quantity:
        raise DomainError(
            "production_plan_inventory_changed",
            f"{item.item_code} {item.item_name}的可用库存已变化，请重新加载并填写生产数量",
            status_code=409,
            path="items",
        )


def _reserve_flow_items(
    session: Session,
    plan: ProductionPlan,
    items: list[ProductionPlanItem],
    shipping_node_id: str,
    required_product_quantity: int,
    actor_username: str,
) -> None:
    sample = items[0]
    flow_record = session.scalar(select(ProductProcessFlow).where(
        ProductProcessFlow.product_id == sample.product_id,
        ProductProcessFlow.product_version == sample.product_version,
    ))
    if flow_record is None:
        raise DomainError("product_engineering_data_missing", "产品版本缺少流程图")
    flow = flow_record.flow_json
    nodes = {node.get("id"): node for node in flow.get("nodes", [])}
    incoming: dict[str, list[str]] = {}
    for edge in flow.get("edges", []):
        incoming.setdefault(edge.get("target_node_id"), []).append(edge.get("source_node_id"))
    by_node = {item.flow_node_id: item for item in items}

    def visit(node_id: str, required_units: int, visiting: set[str]) -> None:
        if node_id in visiting:
            raise DomainError("product_flow_cycle", "产品流程图不能形成循环")
        node = nodes.get(node_id)
        if node is None:
            return
        next_required = required_units
        if node.get("type") in {"assembly", "part"}:
            item = by_node.get(node_id)
            if item is None:
                raise DomainError("production_plan_flow_mismatch", "生产计划与流程图不一致")
            item.gross_required_quantity = required_units * item.unit_requirement
            if node.get("type") == "assembly":
                _reserve_and_validate_plan_item(session, plan, item, actor_username)
                next_required = ceil(item.net_required_quantity / item.unit_requirement)
        for source_id in incoming.get(node_id, []):
            if source_id:
                visit(source_id, next_required, visiting | {node_id})

    visit(shipping_node_id, required_product_quantity, set())
    routes_by_bom: dict[int, list[ProductionPlanItem]] = {}
    for item in items:
        if item.item_type == "part" and item.product_bom_id is not None:
            routes_by_bom.setdefault(item.product_bom_id, []).append(item)
    for routes in routes_by_bom.values():
        routes.sort(key=lambda item: item.sort_order)
        required = max((item.gross_required_quantity for item in routes), default=0)
        for item in routes:
            item.gross_required_quantity = 0
            item.estimated_inventory_quantity = 0
            item.net_required_quantity = 0
            item.reserved_inventory_quantity = 0
        primary = routes[0]
        primary.gross_required_quantity = required
        allocated = reserve_plan_item(
            session,
            production_plan_id=plan.id,
            production_plan_item_id=primary.id,
            plan_item=primary,
            requested_quantity=required,
            actor_username=actor_username,
        )
        primary.reserved_inventory_quantity = allocated
        primary.estimated_inventory_quantity = allocated
        primary.net_required_quantity = required - allocated
        if sum(item.planned_production_quantity for item in routes) < primary.net_required_quantity:
            raise DomainError(
                "production_plan_inventory_changed",
                f"{primary.item_code} {primary.item_name}的可用库存已变化，请重新加载并分配各路线生产数量",
                status_code=409,
                path="items",
            )


__all__ = [
    "cancel_order_plan",
    "confirm_order_plan",
    "get_order_plan",
    "serialize_plan",
    "update_order_plan",
]
