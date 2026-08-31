"""Build and refresh the material plan generated from an order and engineering flow."""

from dataclasses import asdict, dataclass, replace
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.time import utc_now
from modules.engineering.model_api import Product, ProductBom, ProductProcessFlow
from modules.errors import DomainError
from modules.inventory.identity_api import component_identity_key
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_stock_view import plan_item_available_quantities
from modules.planning.route_projection import rebuild_plan_route_tasks


@dataclass(frozen=True, slots=True)
class PlannedIdentity:
    customer_order_id: int
    customer_order_item_id: int
    identity_key: str
    item_type: str
    product_id: int
    product_version: int
    product_bom_id: int | None
    flow_node_id: str
    item_code: str
    item_name: str
    unit_requirement: int
    gross_required_quantity: int
    sort_order: int


def rebuild_order_plan(session: Session, order) -> ProductionPlan:
    plan = session.scalar(
        select(ProductionPlan).where(ProductionPlan.customer_order_id == order.id)
    )
    created = plan is None
    if created:
        plan = ProductionPlan(customer_order_id=order.id)
        session.add(plan)
        session.flush()
    if plan.status != "draft":
        raise DomainError("production_plan_not_editable", "只有未确认生产计划允许重算")
    previous = {
        item.identity_key: item.planned_production_quantity
        for item in plan.items
    }
    plan.items.clear()
    session.flush()
    definitions: list[PlannedIdentity] = []
    for order_index, order_item in enumerate(order.items):
        definitions.extend(_order_item_definitions(session, order_item, order_index))
    availability = plan_item_available_quantities(session, definitions)
    definitions = _apply_flow_inventory(session, definitions, availability)
    for definition in definitions:
        estimated = min(
            definition.gross_required_quantity,
            availability.get(definition.identity_key, 0),
        )
        net_required = definition.gross_required_quantity - estimated
        plan.items.append(ProductionPlanItem(
            **asdict(definition),
            estimated_inventory_quantity=estimated,
            net_required_quantity=net_required,
            planned_production_quantity=max(
                previous.get(definition.identity_key, net_required),
                net_required,
            ),
        ))
    if not created:
        plan.revision += 1
    plan.updated_at = utc_now()
    session.flush()
    rebuild_plan_route_tasks(session, plan)
    return plan


def refresh_plan_availability(session: Session, plan: ProductionPlan) -> None:
    availability = plan_item_available_quantities(session, plan.items)
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in plan.items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    for items in groups.values():
        finished = next(item for item in items if item.item_type == "finished_product")
        finished.estimated_inventory_quantity = min(
            finished.gross_required_quantity,
            availability.get(finished.identity_key, 0),
        )
        finished.net_required_quantity = (
            finished.gross_required_quantity - finished.estimated_inventory_quantity
        )
        finished.planned_production_quantity = finished.net_required_quantity
        gross_quantities = _flow_gross_quantities(
            session,
            items,
            finished.flow_node_id,
            finished.net_required_quantity,
            availability,
        )
        for item in items:
            if item.item_type == "finished_product":
                continue
            item.gross_required_quantity = gross_quantities.get(item.flow_node_id, 0)
            item.estimated_inventory_quantity = min(
                item.gross_required_quantity,
                availability.get(item.identity_key, 0),
            )
            item.net_required_quantity = (
                item.gross_required_quantity - item.estimated_inventory_quantity
            )
            if item.item_type != "part":
                item.planned_production_quantity = item.net_required_quantity


def planned_finished_quantity(session: Session, items: list[ProductionPlanItem]) -> int:
    """Return the order quantity supported by stock plus planned ordinary parts."""
    finished = next(item for item in items if item.item_type == "finished_product")
    availability = {
        item.identity_key: item.estimated_inventory_quantity
        for item in items
    }

    def can_support(quantity: int) -> bool:
        required_from_flow = max(quantity - finished.estimated_inventory_quantity, 0)
        gross_quantities = _flow_gross_quantities(
            session,
            items,
            finished.flow_node_id,
            required_from_flow,
            availability,
        )
        return _parts_support(items, gross_quantities)

    low = 0
    high = finished.gross_required_quantity
    while low < high:
        middle = (low + high + 1) // 2
        if can_support(middle):
            low = middle
        else:
            high = middle - 1
    return low


def planned_product_quantity(items: list[ProductionPlanItem]) -> int:
    """Return the product quantity represented by the saved ordinary-part plan."""
    finished = next(
        (item for item in items if item.item_type == "finished_product"),
        None,
    )
    if finished is None:
        return 0
    parts = [item for item in items if item.item_type == "part"]
    if not parts:
        return 0
    component_capacities = [
        max(
            finished.gross_required_quantity
            + (item.planned_production_quantity - item.net_required_quantity)
            // item.unit_requirement,
            0,
        )
        for item in parts
    ]
    return min(component_capacities)


def _order_item_definitions(session: Session, order_item, order_index: int) -> list[PlannedIdentity]:
    product = session.get(Product, order_item.product_id)
    flow_record = session.scalar(
        select(ProductProcessFlow).where(
            ProductProcessFlow.product_id == order_item.product_id,
            ProductProcessFlow.product_version == order_item.product_version,
        )
    )
    bom_items = list(session.scalars(
        select(ProductBom)
        .where(
            ProductBom.product_id == order_item.product_id,
            ProductBom.product_version == order_item.product_version,
        )
        .order_by(ProductBom.sort_order)
    ))
    if product is None or flow_record is None or not bom_items:
        raise DomainError(
            "product_engineering_data_missing",
            "订单产品版本缺少 BOM 或流程图",
            path="items",
        )
    flow = flow_record.flow_json
    nodes = {node.get("id"): node for node in flow.get("nodes", [])}
    inbound_nodes = sorted(
        (node for node in nodes.values() if node.get("type") == "finished_inbound"),
        key=_node_sort_key,
    )
    if len(inbound_nodes) != 1:
        raise DomainError(
            "product_finished_inbound_node_invalid",
            f"产品 {product.factory_code} 必须有且只有一个入库节点",
            path="items",
        )
    base_sort = order_index * 10000
    finished_node = inbound_nodes[0]
    result = [PlannedIdentity(
        customer_order_id=order_item.customer_order_id,
        customer_order_item_id=order_item.id,
        identity_key=component_identity_key(
            department_code="finished",
            item_type="finished_product",
            product_id=product.id,
            product_version=order_item.product_version,
            product_bom_id=None,
            flow_node_id=finished_node["id"],
        ),
        item_type="finished_product",
        product_id=product.id,
        product_version=order_item.product_version,
        product_bom_id=None,
        flow_node_id=finished_node["id"],
        item_code=product.factory_code,
        item_name=product.product_name,
        unit_requirement=1,
        gross_required_quantity=order_item.quantity,
        sort_order=base_sort,
    )]
    assembly_nodes = sorted(
        (node for node in nodes.values() if node.get("type") == "assembly"),
        key=_node_sort_key,
    )
    for index, node in enumerate(assembly_nodes, start=1):
        sequence = int(node.get("assembly_sequence") or 80 + index)
        code = node.get("assembly_code") or f"{product.factory_code}-{sequence}"
        name = node.get("assembly_name") or node.get("output_name") or "装配体"
        unit_requirement = max(int(node.get("output_pcs") or 1), 1)
        result.append(PlannedIdentity(
            customer_order_id=order_item.customer_order_id,
            customer_order_item_id=order_item.id,
            identity_key=component_identity_key(
                department_code="warehouse",
                item_type="assembly",
                product_id=product.id,
                product_version=order_item.product_version,
                product_bom_id=None,
                flow_node_id=node["id"],
            ),
            item_type="assembly",
            product_id=product.id,
            product_version=order_item.product_version,
            product_bom_id=None,
            flow_node_id=node["id"],
            item_code=code,
            item_name=name,
            unit_requirement=unit_requirement,
            gross_required_quantity=order_item.quantity * unit_requirement,
            sort_order=base_sort + index,
        ))
    part_nodes: dict[int, list[dict]] = {}
    for node in nodes.values():
        if node.get("type") == "part":
            part_nodes.setdefault(node.get("bom_item_id"), []).append(node)
    for index, bom in enumerate(bom_items, start=1):
        part_routes = part_nodes.get(bom.id, [])
        if len(part_routes) != 1:
            raise DomainError(
                "product_flow_bom_invalid",
                f"配件 {bom.part_name} 必须且只能有一个流程节点",
                path="items",
            )
        node = part_routes[0]
        result.append(PlannedIdentity(
            customer_order_id=order_item.customer_order_id,
            customer_order_item_id=order_item.id,
            identity_key=component_identity_key(
                department_code="warehouse",
                item_type="part",
                product_id=product.id,
                product_version=order_item.product_version,
                product_bom_id=bom.id,
                flow_node_id=node["id"],
            ),
            item_type="part",
            product_id=product.id,
            product_version=order_item.product_version,
            product_bom_id=bom.id,
            flow_node_id=node["id"],
            item_code=bom.part_no,
            item_name=bom.part_name,
            unit_requirement=bom.pcs,
            gross_required_quantity=order_item.quantity * bom.pcs,
            sort_order=base_sort + 1000 + index * 10,
        ))
    return result


def _apply_flow_inventory(
    session: Session,
    definitions: list[PlannedIdentity],
    availability: dict[str, int],
) -> list[PlannedIdentity]:
    """Net stock from finished goods down through each assembly level."""
    groups: dict[int, list[PlannedIdentity]] = {}
    for definition in definitions:
        groups.setdefault(definition.customer_order_item_id, []).append(definition)
    result: list[PlannedIdentity] = []
    for items in groups.values():
        finished = next(item for item in items if item.item_type == "finished_product")
        finished_net = finished.gross_required_quantity - min(
            finished.gross_required_quantity,
            availability.get(finished.identity_key, 0),
        )
        gross_quantities = _flow_gross_quantities(
            session,
            items,
            finished.flow_node_id,
            finished_net,
            availability,
        )
        result.extend(
            item if item.item_type == "finished_product" else replace(
                item,
                gross_required_quantity=gross_quantities.get(item.flow_node_id, 0),
            )
            for item in items
        )
    return result


def _flow_gross_quantities(
    session: Session,
    items,
    inbound_node_id: str,
    required_product_quantity: int,
    availability: dict[str, int],
) -> dict[str, int]:
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
    gross: dict[str, int] = {}

    def visit(node_id: str, required_units: int, visiting: set[str]) -> None:
        if node_id in visiting:
            raise DomainError("product_flow_cycle", "产品流程图不能形成循环")
        node = nodes.get(node_id)
        if node is None:
            return
        node_type = node.get("type")
        next_required = required_units
        if node_type in {"assembly", "part"}:
            item = by_node.get(node_id)
            if item is None:
                raise DomainError("production_plan_flow_mismatch", "生产计划与流程图不一致")
            required_quantity = required_units * item.unit_requirement
            gross[node_id] = max(gross.get(node_id, 0), required_quantity)
            if node_type == "assembly":
                available = min(required_quantity, availability.get(item.identity_key, 0))
                next_required = ceil((required_quantity - available) / item.unit_requirement)
        for source_id in incoming.get(node_id, []):
            if source_id:
                visit(source_id, next_required, visiting | {node_id})

    visit(inbound_node_id, required_product_quantity, set())
    return gross


def _parts_support(items, gross: dict[str, int]) -> bool:
    return all(
        gross.get(item.flow_node_id, 0)
        <= item.estimated_inventory_quantity + item.planned_production_quantity
        for item in items
        if item.item_type == "part"
    )


def _node_sort_key(node: dict) -> tuple[float, float, str]:
    return (float(node.get("x") or 0), float(node.get("y") or 0), str(node.get("id") or ""))


__all__ = [
    "planned_finished_quantity",
    "planned_product_quantity",
    "rebuild_order_plan",
    "refresh_plan_availability",
]
