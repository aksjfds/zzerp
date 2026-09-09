"""Procedure configuration and piece-price read models."""

from collections import defaultdict

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.time import business_iso
from modules.engineering.model_api import Product, ProductBom, ProductRouteTask
from modules.errors import DomainError
from modules.organization.read_api import ProcedureRoute, WorkshopView, get_department_procedure_routes, get_workshop_views
from modules.production_core.reference_api import (
    TemporaryWorkOrderPriceReference,
    list_standard_execution_config_keys,
    temporary_work_order_price_references,
)
from modules.standard_execution.persistence import ProcedureConfiguration, ProcedurePrice, ProcedurePriceRevision, WorkOrderPayDetail
from modules.standard_execution.price_config_support import _department, _material_key


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
        procedure_routes = get_department_procedure_routes(session, department.id)
        procedure_by_id = {item.id: item for item in procedure_routes}
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
        formal_total = session.scalar(
            select(func.count()).select_from(candidate.order_by(None).subquery())
        ) or 0
        global_offset = (page - 1) * page_size
        temporary_references, temporary_total = temporary_work_order_price_references(
            session,
            procedure_ids=set(procedure_by_id),
            offset=global_offset,
            limit=page_size,
            keyword=keyword,
        )
        formal_limit = page_size - len(temporary_references)
        formal_offset = max(global_offset - temporary_total, 0)
        candidate_rows = list(session.execute(
            candidate
            .order_by(
                Product.updated_at.desc(),
                Product.id.desc(),
                ProductRouteTask.origin_flow_node_id,
                ProductRouteTask.route_order,
                ProductRouteTask.id,
            )
            .offset(formal_offset)
            .limit(formal_limit)
        )) if formal_limit else []
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
        temporary_rows = _temporary_work_order_price_rows(
            session,
            temporary_references,
            procedure_by_id,
            workshops,
        )
        formal_rows = _formal_procedure_price_rows(
            session,
            selected,
            procedure_routes,
        )
        return [*temporary_rows, *formal_rows], temporary_total + formal_total


def _formal_procedure_price_rows(
    session: Session,
    selected: list[dict],
    procedure_routes: list[ProcedureRoute],
) -> list[dict]:
    workshop_ids = {item["workshop"].id for item in selected}
    procedures_by_workshop: dict[int, list[ProcedureRoute]] = defaultdict(list)
    for procedure in procedure_routes:
        if procedure.workshop_id in workshop_ids:
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
    order_scope_keys = {reference[:4] for reference in referenced}
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
            "row_type": "formal",
            "product_id": product.id, "product_version": product.version,
            "product_name": product.product_name, "factory_code": product.factory_code,
            "product_bom_id": bom.id if bom else None,
            "origin_flow_node_id": origin_id, "flow_node_id": flow_node_id,
            "workshop_id": item["workshop"].id,
            "workshop_name": item["workshop"].workshop_name,
            "part_name": item["part_name"], "part_no": item["part_no"],
            "confirmed": configuration is not None and configuration.confirmed_at is not None,
            "can_cancel": (
                configuration is not None
                and configuration.confirmed_at is not None
                and (product.id, product.version, origin_id, flow_node_id)
                not in order_scope_keys
            ),
            "confirmed_at": business_iso(configuration.confirmed_at) if configuration else None,
            "confirmed_by": configuration.confirmed_by if configuration else None,
            "procedures": procedure_data,
        })
    return data


def _temporary_work_order_price_rows(
    session: Session,
    references: list[TemporaryWorkOrderPriceReference],
    procedure_by_id: dict[int, ProcedureRoute],
    workshops: dict[int, WorkshopView],
) -> list[dict]:
    if not references:
        return []
    position_keys = {
        (item.product_id, item.product_version, item.origin_flow_node_id, item.flow_node_id)
        for item in references
    }
    route_rows = session.execute(
        select(ProductRouteTask, Product)
        .join(Product, Product.id == ProductRouteTask.product_id)
        .where(tuple_(
            ProductRouteTask.product_id,
            ProductRouteTask.product_version,
            ProductRouteTask.origin_flow_node_id,
            ProductRouteTask.route_flow_node_id,
        ).in_(position_keys))
    )
    route_by_position = {
        (route.product_id, route.product_version, route.origin_flow_node_id, route.route_flow_node_id):
        (route, product)
        for route, product in route_rows
    }
    order_ids = [item.id for item in references]
    pay_detail_by_order = {
        item.work_order_id: item
        for item in session.scalars(
            select(WorkOrderPayDetail).where(WorkOrderPayDetail.work_order_id.in_(order_ids))
        )
    }
    data: list[dict] = []
    for reference in references:
        position_key = (
            reference.product_id,
            reference.product_version,
            reference.origin_flow_node_id,
            reference.flow_node_id,
        )
        route_row = route_by_position.get(position_key)
        procedure = procedure_by_id.get(reference.procedure_id)
        pay_detail = pay_detail_by_order.get(reference.id)
        workshop = workshops.get(procedure.workshop_id) if procedure else None
        if route_row is None or procedure is None or workshop is None or pay_detail is None:
            raise DomainError(
                "temporary_work_order_price_context_invalid",
                "临时工单计价信息不完整",
                status_code=409,
            )
        route, product = route_row
        data.append({
            "row_type": "temporary",
            "work_order_id": reference.id,
            "work_order_no": reference.work_order_no,
            "product_id": reference.product_id,
            "product_version": reference.product_version,
            "origin_flow_node_id": reference.origin_flow_node_id,
            "flow_node_id": reference.flow_node_id,
            "product_name": product.product_name,
            "factory_code": product.factory_code,
            "part_name": route.origin_item_name,
            "part_no": route.origin_item_code,
            "workshop_name": workshop.workshop_name,
            "procedure_name": pay_detail.procedure_name,
            "unit_price": pay_detail.unit_price,
            "status": reference.status,
            "created_at": business_iso(reference.created_at),
        })
    return data


def list_procedure_price_revisions(
    department_code: str,
    page: int,
    page_size: int,
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
        base = select(ProcedurePriceRevision).where(
            ProcedurePriceRevision.department_id == department.id
        )
        total = session.scalar(
            select(func.count(ProcedurePriceRevision.id)).where(
                ProcedurePriceRevision.department_id == department.id
            )
        ) or 0
        rows = list(session.scalars(
            base.order_by(
                ProcedurePriceRevision.created_at.desc(),
                ProcedurePriceRevision.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        return [
            {
                "id": item.id,
                "target_type": item.target_type,
                "target_label": item.target_label,
                "previous_unit_price": item.previous_unit_price,
                "new_unit_price": item.new_unit_price,
                "actor_username": item.actor_username,
                "created_at": business_iso(item.created_at),
            }
            for item in rows
        ], total
