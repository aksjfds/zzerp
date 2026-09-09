"""Shared scope resolution and revision recording for procedure configuration."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select

from domain.identity import can_access_department
from modules.engineering.model_api import Product
from modules.engineering.pricing_api import get_product_pricing_view
from modules.errors import DomainError
from modules.organization.read_api import DepartmentView, get_department_views_by_codes, get_workshop_views
from modules.standard_execution.persistence import ProcedurePriceRevision


@dataclass(frozen=True, slots=True)
class _ConfigurationScope:
    department_id: int
    material_key: str
    workshop_id: int
    expected_input_mode: str
    target_prefix: str


def _record_price_revision(
    session,
    *,
    department_id: int,
    target_type: str,
    target_id: int,
    target_label: str,
    previous_unit_price,
    new_unit_price,
    actor_username: str,
) -> None:
    if previous_unit_price == new_unit_price:
        return
    session.add(ProcedurePriceRevision(
        department_id=department_id,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        previous_unit_price=previous_unit_price,
        new_unit_price=new_unit_price,
        actor_username=actor_username,
    ))


def _reachable_workshop_nodes(flow: dict, origin_id: str) -> list[dict]:
    nodes = {str(node.get("id")): node for node in flow.get("nodes", []) if node.get("id")}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in flow.get("edges", []):
        source = str(edge.get("source_node_id") or "")
        target = str(edge.get("target_node_id") or "")
        if source and target:
            outgoing[source].append(target)
    origin = nodes.get(origin_id)
    result: list[dict] = []
    if (
        origin is not None
        and origin.get("type") == "assembly"
        and isinstance(origin.get("workshop_id"), int)
    ):
        result.append(origin)
    queue = list(outgoing.get(origin_id, []))
    visited: set[str] = set()
    while queue:
        node_id = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        node = nodes.get(node_id)
        if node is None:
            continue
        if node.get("type") in {"assembly", "finished_inbound"}:
            continue
        if node.get("type") == "process" and isinstance(node.get("workshop_id"), int):
            result.append(node)
        queue.extend(outgoing.get(node_id, []))
    return result


def _material_key(product_bom_id: int | None, origin_flow_node_id: str) -> str:
    return f"part:{product_bom_id}" if product_bom_id is not None else f"assembly:{origin_flow_node_id}"


def _resolve_configuration_scope(
    session,
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    user_department: str | None,
    user_is_system: bool,
) -> _ConfigurationScope:
    department = _department(
        session,
        department_code,
        user_department,
        user_is_system,
    )
    product = get_product_pricing_view(session, product_id, product_version)
    if product is None:
        raise DomainError("product_version_not_found", "产品版本不存在", status_code=404)
    session.execute(
        select(Product.id).where(Product.id == product_id).with_for_update()
    )
    nodes = {
        str(node.get("id")): node
        for node in (product.flow_json or {}).get("nodes", [])
    }
    origin, node = nodes.get(origin_flow_node_id), nodes.get(flow_node_id)
    reachable_ids = {
        str(item.get("id"))
        for item in _reachable_workshop_nodes(
            product.flow_json or {},
            origin_flow_node_id,
        )
    }
    if origin is None or node is None or flow_node_id not in reachable_ids:
        raise DomainError("procedure_price_route_invalid", "当前物料不经过该车间节点")
    workshop = next(iter(get_workshop_views(
        session,
        workshop_ids={node.get("workshop_id")},
    )), None)
    if workshop is None or workshop.department_id != department.id:
        raise DomainError("procedure_price_workshop_invalid", "当前车间不属于该部门")
    bom_id = origin.get("bom_item_id") if origin.get("type") == "part" else None
    return _ConfigurationScope(
        department_id=department.id,
        material_key=_material_key(bom_id, origin_flow_node_id),
        workshop_id=workshop.id,
        expected_input_mode="multiple" if node.get("type") == "assembly" else "single",
        target_prefix=(
            f"{product.factory_code}-{product.product_name} · "
            f"{origin.get('part_no') or origin.get('assembly_code') or ''} "
            f"{origin.get('label') or ''} · {workshop.workshop_name}"
        ).strip(),
    )


def _department(
    session,
    code: str,
    user_department: str | None,
    user_is_system: bool,
) -> DepartmentView:
    department = next(iter(get_department_views_by_codes(session, {code})), None)
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    if not can_access_department(user_department, user_is_system, code):
        raise DomainError("department_access_denied", "无权维护该部门配置", status_code=403)
    return department
