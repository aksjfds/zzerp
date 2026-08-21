from collections import defaultdict

from sqlalchemy import select, update

from database import SessionLocal
from modules.engineering.pricing_api import get_product_pricing_view, list_current_product_pricing_views
from modules.errors import DomainError
from modules.organization.persistence import Department, Procedure, Workshop
from modules.production_core.persistence import ProductionItem, WorkOrder
from modules.standard_execution.persistence import ProcedurePrice, WorkOrderPayDetail
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
        if node.get("type") in {"assembly", "shipping"}:
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
    user_department: str,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = _department(session, department_code, user_department)
        workshops = {
            item.id: item for item in session.scalars(
                select(Workshop).where(Workshop.department_id == department.id)
                .order_by(Workshop.workshop_name, Workshop.id)
            )
        }
        value = (keyword or "").strip().lower()
        candidates: list[dict] = []
        seen: set[tuple[int, int, str, str]] = set()
        for product in list_current_product_pricing_views(session):
            boms = {bom.id: bom for bom in product.boms}
            for origin in (product.flow_json or {}).get("nodes", []):
                if origin.get("type") not in {"part", "assembly"}:
                    continue
                bom = boms.get(origin.get("bom_item_id")) if origin.get("type") == "part" else None
                if origin.get("type") == "part" and bom is None:
                    continue
                origin_id = str(origin.get("id") or "")
                part_name = bom.part_name if bom else (origin.get("output_name") or origin.get("label") or "装配体")
                part_no = bom.part_no if bom else part_name
                searchable = " ".join((product.product_name, product.factory_code, part_name, part_no)).lower()
                if value and value not in searchable:
                    continue
                for node in _reachable_workshop_nodes(product.flow_json or {}, origin_id):
                    workshop = workshops.get(node.get("workshop_id"))
                    if workshop is None:
                        continue
                    key = (product.product_id, product.product_version, origin_id, str(node["id"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append({
                        "product": product, "bom": bom, "origin_id": origin_id,
                        "flow_node_id": str(node["id"]), "workshop": workshop,
                        "part_name": part_name, "part_no": part_no,
                    })
        total = len(candidates)
        selected = candidates[(page - 1) * page_size:page * page_size]
        workshop_ids = {item["workshop"].id for item in selected}
        procedures_by_workshop: dict[int, list[Procedure]] = defaultdict(list)
        if workshop_ids:
            for procedure in session.scalars(
                select(Procedure).where(Procedure.workshop_id.in_(workshop_ids))
                .order_by(Procedure.procedure_name, Procedure.id)
            ):
                procedures_by_workshop[procedure.workshop_id].append(procedure)
        product_ids = {item["product"].product_id for item in selected}
        prices = list(session.scalars(
            select(ProcedurePrice).where(ProcedurePrice.product_id.in_(product_ids))
        )) if product_ids else []
        price_by_scope = {
            (item.product_id, item.product_version, item.material_key, item.flow_node_id, item.procedure_id): item.unit_price
            for item in prices
        }
        referenced = set(session.execute(
            select(
                ProductionItem.product_id, ProductionItem.product_version,
                ProductionItem.origin_flow_node_id, WorkOrder.flow_node_id, WorkOrder.procedure_id,
            ).join(WorkOrder, WorkOrder.production_item_id == ProductionItem.id)
            .where(ProductionItem.product_id.in_(product_ids))
        )) if product_ids else set()
        data: list[dict] = []
        for item in selected:
            product, bom = item["product"], item["bom"]
            origin_id, flow_node_id = item["origin_id"], item["flow_node_id"]
            material_key = _material_key(bom.id if bom else None, origin_id)
            procedure_data = []
            for procedure in procedures_by_workshop[item["workshop"].id]:
                ref_key = (product.product_id, product.product_version, origin_id, flow_node_id, procedure.id)
                price_key = (product.product_id, product.product_version, material_key, flow_node_id, procedure.id)
                if price_key not in price_by_scope and ref_key not in referenced:
                    continue
                procedure_data.append({
                    "procedure_id": procedure.id,
                    "procedure_name": procedure.procedure_name,
                    "unit_price": price_by_scope.get(price_key),
                    "referenced": ref_key in referenced,
                })
            data.append({
                "product_id": product.product_id, "product_version": product.product_version,
                "product_name": product.product_name, "factory_code": product.factory_code,
                "product_bom_id": bom.id if bom else None,
                "origin_flow_node_id": origin_id, "flow_node_id": flow_node_id,
                "workshop_id": item["workshop"].id,
                "workshop_name": item["workshop"].workshop_name,
                "part_name": item["part_name"], "part_no": item["part_no"],
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
    user_department: str,
) -> None:
    with SessionLocal.begin() as session:
        department = _department(session, department_code, user_department)
        product = get_product_pricing_view(session, product_id, product_version)
        if product is None:
            raise DomainError("product_version_not_found", "产品版本不存在", status_code=404)
        nodes = {str(node.get("id")): node for node in (product.flow_json or {}).get("nodes", [])}
        origin, node = nodes.get(origin_flow_node_id), nodes.get(flow_node_id)
        reachable_ids = {str(item.get("id")) for item in _reachable_workshop_nodes(product.flow_json or {}, origin_flow_node_id)}
        if origin is None or node is None or flow_node_id not in reachable_ids:
            raise DomainError("procedure_price_route_invalid", "当前物料不经过该车间节点")
        workshop = session.get(Workshop, node.get("workshop_id"), with_for_update=True)
        if workshop is None or workshop.department_id != department.id:
            raise DomainError("procedure_price_workshop_invalid", "当前车间不属于该部门")
        bom_id = origin.get("bom_item_id") if origin.get("type") == "part" else None
        material_key = _material_key(bom_id, origin_flow_node_id)
        expected_type = (
            "purchase_receipt"
            if department.department_code == "purchasing"
            else "standard"
        )
        expected_input_mode = "multiple" if node.get("type") == "assembly" else "single"
        normalized: dict[str, tuple[int | None, object]] = {}
        for item in payload.procedures:
            name = item.procedure_name.strip()
            if name in normalized:
                raise DomainError("procedure_name_duplicate", "同一车间不能重复配置同名工艺")
            normalized[name] = (item.procedure_id, item.unit_price)
        existing_prices = list(session.scalars(
            select(ProcedurePrice).where(
                ProcedurePrice.product_id == product_id,
                ProcedurePrice.product_version == product_version,
                ProcedurePrice.material_key == material_key,
                ProcedurePrice.flow_node_id == flow_node_id,
            ).with_for_update()
        ))
        existing_by_procedure = {item.procedure_id: item for item in existing_prices}
        retained_ids: set[int] = set()
        for name, (procedure_id, unit_price) in normalized.items():
            procedure = session.get(Procedure, procedure_id, with_for_update=True) if procedure_id else None
            if procedure is None:
                procedure = session.scalar(select(Procedure).where(
                    Procedure.workshop_id == workshop.id,
                    Procedure.procedure_name == name,
                ).with_for_update())
            if procedure is None:
                procedure = Procedure(
                    workshop_id=workshop.id, procedure_name=name,
                    procedure_type=expected_type,
                    input_mode=expected_input_mode,
                )
                session.add(procedure)
                session.flush()
            if (
                procedure.workshop_id != workshop.id
                or procedure.procedure_name != name
                or procedure.procedure_type != expected_type
                or procedure.input_mode != expected_input_mode
            ):
                raise DomainError("procedure_workshop_invalid", "所选工艺不属于当前车间")
            retained_ids.add(procedure.id)
            price = existing_by_procedure.get(procedure.id)
            if price is None:
                session.add(ProcedurePrice(
                    product_id=product_id, product_version=product_version,
                    material_key=material_key, flow_node_id=flow_node_id,
                    procedure_id=procedure.id, unit_price=unit_price,
                ))
            else:
                price.unit_price = unit_price
            session.execute(update(WorkOrderPayDetail).where(
                WorkOrderPayDetail.procedure_id == procedure.id,
                WorkOrderPayDetail.work_order_id.in_(
                    select(WorkOrder.id).join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id).where(
                        ProductionItem.product_id == product_id,
                        ProductionItem.product_version == product_version,
                        ProductionItem.origin_flow_node_id == origin_flow_node_id,
                        WorkOrder.flow_node_id == flow_node_id,
                    )
                ),
            ).values(unit_price=unit_price))
        for price in existing_prices:
            if price.procedure_id in retained_ids:
                continue
            referenced = session.scalar(select(WorkOrder.id).join(
                ProductionItem, ProductionItem.id == WorkOrder.production_item_id
            ).where(
                ProductionItem.product_id == product_id,
                ProductionItem.product_version == product_version,
                ProductionItem.origin_flow_node_id == origin_flow_node_id,
                WorkOrder.flow_node_id == flow_node_id,
                WorkOrder.procedure_id == price.procedure_id,
            ).limit(1))
            if referenced is not None:
                raise DomainError("procedure_referenced", "已被工单引用的工艺不能删除")
            procedure = session.get(Procedure, price.procedure_id, with_for_update=True)
            session.delete(price)
            session.flush()
            if procedure is not None:
                has_price = session.scalar(select(ProcedurePrice.id).where(ProcedurePrice.procedure_id == procedure.id).limit(1))
                has_order = session.scalar(select(WorkOrder.id).where(WorkOrder.procedure_id == procedure.id).limit(1))
                if has_price is None and has_order is None:
                    session.delete(procedure)


def _department(session, code: str, user_department: str) -> Department:
    department = session.scalar(select(Department).where(Department.department_code == code))
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    if user_department not in {"sys", code}:
        raise DomainError("department_access_denied", "无权维护该部门配置", status_code=403)
    return department
