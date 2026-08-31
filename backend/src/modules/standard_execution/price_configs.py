from collections import defaultdict

from sqlalchemy import func, or_, select, update

from database import SessionLocal
from domain.identity import can_access_department
from domain.time import business_iso, utc_now
from modules.engineering.model_api import Product, ProductBom, ProductRouteTask
from modules.engineering.pricing_api import get_product_pricing_view
from modules.errors import DomainError
from modules.organization.read_api import (
    DepartmentView,
    ProcedureRoute,
    get_department_procedure_routes,
    get_department_views_by_codes,
    get_workshop_views,
)
from modules.organization.transaction_api import delete_procedure, resolve_workshop_procedure
from modules.production_core.reference_api import (
    has_standard_execution_order,
    has_work_order_for_procedure,
    list_standard_execution_config_keys,
    list_standard_execution_order_ids,
)
from modules.standard_execution.persistence import (
    ProcedureConfiguration,
    ProcedurePrice,
    WorkOrderPayDetail,
)
from schemas.procedure_prices import ProcedurePriceUpdate


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


def list_procedure_prices(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None,
    user_department: str | None,
    user_is_system: bool,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = _department(
            session,
            department_code,
            user_department,
            user_is_system,
        )
        workshops = {
            item.id: item
            for item in get_workshop_views(
                session,
                department_ids={department.id},
            )
        }
        workshop_ids_for_department = set(workshops)
        candidate = (
            select(ProductRouteTask, Product, ProductBom)
            .join(Product, Product.id == ProductRouteTask.product_id)
            .outerjoin(ProductBom, ProductBom.id == ProductRouteTask.product_bom_id)
            .where(
                ProductRouteTask.workshop_id.in_(workshop_ids_for_department),
                Product.version == ProductRouteTask.product_version,
                or_(
                    ProductRouteTask.route_node_type != "assembly",
                    ProductRouteTask.origin_node_type == "assembly",
                ),
            )
        )
        value = (keyword or "").strip()
        if value:
            pattern = f"%{value}%"
            candidate = candidate.where(or_(
                Product.product_name.ilike(pattern),
                Product.factory_code.ilike(pattern),
                ProductRouteTask.origin_item_name.ilike(pattern),
                ProductRouteTask.origin_item_code.ilike(pattern),
            ))
        total = session.scalar(
            select(func.count()).select_from(candidate.order_by(None).subquery())
        ) or 0
        candidate_rows = list(session.execute(
            candidate
            .order_by(
                Product.updated_at.desc(),
                Product.id.desc(),
                ProductRouteTask.origin_flow_node_id,
                ProductRouteTask.route_order,
                ProductRouteTask.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        selected = [
            {
                "product": product,
                "bom": bom,
                "origin_id": route.origin_flow_node_id,
                "flow_node_id": route.route_flow_node_id,
                "workshop": workshops[route.workshop_id],
                "part_name": route.origin_item_name,
                "part_no": route.origin_item_code,
            }
            for route, product, bom in candidate_rows
        ]
        workshop_ids = {item["workshop"].id for item in selected}
        procedures_by_workshop: dict[int, list[ProcedureRoute]] = defaultdict(list)
        if workshop_ids:
            for procedure in get_department_procedure_routes(session, department.id):
                if procedure.workshop_id not in workshop_ids:
                    continue
                procedures_by_workshop[procedure.workshop_id].append(procedure)
        product_ids = {item["product"].id for item in selected}
        configurations = list(session.scalars(
            select(ProcedureConfiguration).where(
                ProcedureConfiguration.product_id.in_(product_ids)
            )
        )) if product_ids else []
        configuration_by_scope = {
            (item.product_id, item.product_version, item.material_key, item.flow_node_id): item
            for item in configurations
        }
        configuration_ids = {item.id for item in configurations}
        prices = list(session.scalars(
            select(ProcedurePrice).where(
                ProcedurePrice.configuration_id.in_(configuration_ids)
            )
        )) if configuration_ids else []
        price_by_scope = {
            (item.configuration_id, item.procedure_id): item.unit_price
            for item in prices
        }
        procedure_ids = {
            procedure.id
            for procedures in procedures_by_workshop.values()
            for procedure in procedures
        }
        referenced = list_standard_execution_config_keys(
            session,
            product_ids,
            procedure_ids,
        )
        data: list[dict] = []
        for item in selected:
            product, bom = item["product"], item["bom"]
            origin_id, flow_node_id = item["origin_id"], item["flow_node_id"]
            material_key = _material_key(bom.id if bom else None, origin_id)
            configuration = configuration_by_scope.get(
                (product.id, product.version, material_key, flow_node_id)
            )
            procedure_data = []
            for procedure in procedures_by_workshop[item["workshop"].id]:
                ref_key = (product.id, product.version, origin_id, flow_node_id, procedure.id)
                price_key = (configuration.id, procedure.id) if configuration else None
                if price_key not in price_by_scope:
                    continue
                procedure_data.append({
                    "procedure_id": procedure.id,
                    "procedure_name": procedure.procedure_name,
                    "unit_price": price_by_scope.get(price_key),
                    "referenced": ref_key in referenced,
                })
            data.append({
                "product_id": product.id, "product_version": product.version,
                "product_name": product.product_name, "factory_code": product.factory_code,
                "product_bom_id": bom.id if bom else None,
                "origin_flow_node_id": origin_id, "flow_node_id": flow_node_id,
                "workshop_id": item["workshop"].id,
                "workshop_name": item["workshop"].workshop_name,
                "part_name": item["part_name"], "part_no": item["part_no"],
                "confirmed": configuration is not None and configuration.confirmed_at is not None,
                "confirmed_at": business_iso(configuration.confirmed_at) if configuration else None,
                "confirmed_by": configuration.confirmed_by if configuration else None,
                "procedures": procedure_data,
            })
        return data, total


def update_procedure_price(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> None:
    with SessionLocal.begin() as session:
        _save_procedure_configuration(
            session,
            department_code,
            product_id,
            product_version,
            origin_flow_node_id,
            flow_node_id,
            payload,
            user_department,
            user_is_system,
            actor_username,
            confirm=False,
        )


def confirm_procedure_configuration(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> None:
    with SessionLocal.begin() as session:
        _save_procedure_configuration(
            session,
            department_code,
            product_id,
            product_version,
            origin_flow_node_id,
            flow_node_id,
            payload,
            user_department,
            user_is_system,
            actor_username,
            confirm=True,
        )


def _save_procedure_configuration(
    session,
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
    *,
    confirm: bool,
) -> None:
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
    nodes = {str(node.get("id")): node for node in (product.flow_json or {}).get("nodes", [])}
    origin, node = nodes.get(origin_flow_node_id), nodes.get(flow_node_id)
    reachable_ids = {str(item.get("id")) for item in _reachable_workshop_nodes(product.flow_json or {}, origin_flow_node_id)}
    if origin is None or node is None or flow_node_id not in reachable_ids:
        raise DomainError("procedure_price_route_invalid", "当前物料不经过该车间节点")
    workshop = next(iter(get_workshop_views(
        session,
        workshop_ids={node.get("workshop_id")},
    )), None)
    if workshop is None or workshop.department_id != department.id:
        raise DomainError("procedure_price_workshop_invalid", "当前车间不属于该部门")
    bom_id = origin.get("bom_item_id") if origin.get("type") == "part" else None
    material_key = _material_key(bom_id, origin_flow_node_id)
    expected_input_mode = "multiple" if node.get("type") == "assembly" else "single"
    scoped_order_ids = list_standard_execution_order_ids(
        session,
        product_id=product_id,
        product_version=product_version,
        origin_flow_node_id=origin_flow_node_id,
        flow_node_id=flow_node_id,
    )
    normalized: dict[str, tuple[int | None, object]] = {}
    for item in payload.procedures:
        name = item.procedure_name.strip()
        if name in normalized:
            raise DomainError("procedure_name_duplicate", "同一车间不能重复配置同名工艺")
        normalized[name] = (item.procedure_id, item.unit_price)
    configuration = session.scalar(
        select(ProcedureConfiguration).where(
            ProcedureConfiguration.product_id == product_id,
            ProcedureConfiguration.product_version == product_version,
            ProcedureConfiguration.material_key == material_key,
            ProcedureConfiguration.flow_node_id == flow_node_id,
        ).with_for_update()
    )
    if configuration is None:
        configuration = ProcedureConfiguration(
            product_id=product_id,
            product_version=product_version,
            material_key=material_key,
            flow_node_id=flow_node_id,
        )
        session.add(configuration)
        session.flush()
    existing_prices = list(session.scalars(
        select(ProcedurePrice).where(
            ProcedurePrice.configuration_id == configuration.id,
        ).with_for_update()
    ))
    existing_by_procedure = {item.procedure_id: item for item in existing_prices}
    if configuration.confirmed_at is not None:
        submitted_ids = {
            item.procedure_id for item in payload.procedures
            if item.procedure_id is not None
        }
        if (
            len(submitted_ids) != len(payload.procedures)
            or submitted_ids != set(existing_by_procedure)
        ):
            raise DomainError(
                "procedure_configuration_locked",
                "工艺配置已确认，不能修改工艺清单",
                status_code=409,
            )
    retained_ids: set[int] = set()
    for name, (procedure_id, unit_price) in normalized.items():
        procedure = resolve_workshop_procedure(
            session,
            workshop_id=workshop.id,
            procedure_id=procedure_id,
            procedure_name=name if procedure_id is None else None,
            required_input_mode=expected_input_mode,
        )
        if (
            procedure.workshop_id != workshop.id
            or procedure.procedure_name != name
        ):
            raise DomainError("procedure_workshop_invalid", "所选工艺不属于当前车间")
        retained_ids.add(procedure.id)
        price = existing_by_procedure.get(procedure.id)
        if price is None:
            session.add(ProcedurePrice(
                configuration_id=configuration.id,
                procedure_id=procedure.id, unit_price=unit_price,
            ))
        else:
            price.unit_price = unit_price
        if scoped_order_ids:
            session.execute(update(WorkOrderPayDetail).where(
                WorkOrderPayDetail.procedure_id == procedure.id,
                WorkOrderPayDetail.work_order_id.in_(scoped_order_ids),
            ).values(unit_price=unit_price))
    for price in existing_prices:
        if price.procedure_id in retained_ids:
            continue
        if has_standard_execution_order(
            session,
            product_id=product_id,
            product_version=product_version,
            origin_flow_node_id=origin_flow_node_id,
            flow_node_id=flow_node_id,
            procedure_id=price.procedure_id,
        ):
            raise DomainError("procedure_referenced", "已被工单引用的工艺不能删除")
        procedure_id = price.procedure_id
        session.delete(price)
        session.flush()
        has_price = session.scalar(
            select(ProcedurePrice.id)
            .where(ProcedurePrice.procedure_id == procedure_id)
            .limit(1)
        )
        if (
            has_price is None
            and not has_work_order_for_procedure(session, procedure_id)
        ):
            delete_procedure(session, procedure_id)
    if confirm:
        if configuration.confirmed_at is not None:
            raise DomainError(
                "procedure_configuration_already_confirmed",
                "工艺配置已经确认",
                status_code=409,
            )
        if not retained_ids:
            raise DomainError(
                "procedure_configuration_empty",
                "至少配置一个工艺后才能确认",
            )
        session.flush()
        configuration.confirmed_at = utc_now()
        configuration.confirmed_by = actor_username


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
