from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, select

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow, ProductVersion
from models.organization import (
    Department,
    Procedure,
    ProcedureTag,
    ProcedureTagPrice,
    Workshop,
)
from models.production import ProductionItem, WorkOrder
from schemas.procedure_tag_prices import ProcedureTagPriceUpdate
from services.errors import DomainError
from services.procedure_tags import get_or_create_tag
from services.production_flow import origin_route_procedure_ids


def list_procedure_tag_prices(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None,
    user_department: str,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = _department(session, department_code, user_department)
        procedures = list(session.scalars(
            select(Procedure)
            .join(Workshop, Workshop.id == Procedure.workshop_id)
            .where(
                Workshop.department_id == department.id,
                Procedure.procedure_type == "standard",
            )
            .order_by(Procedure.procedure_name, Procedure.id)
        ).all())
        procedures_by_id = {item.id: item for item in procedures}
        if not procedures_by_id:
            return [], 0

        statement = (
            select(Product, ProductProcessFlow)
            .join(
                ProductProcessFlow,
                and_(
                    ProductProcessFlow.product_id == Product.id,
                    ProductProcessFlow.product_version == Product.version,
                ),
            )
            .order_by(Product.updated_at.desc(), Product.id.desc())
        )
        value = (keyword or "").strip()
        candidates: list[dict] = []
        for product, flow_record in session.execute(statement):
            boms = {
                bom.id: bom
                for bom in session.scalars(
                    select(ProductBom).where(
                        ProductBom.product_id == product.id,
                        ProductBom.product_version == product.version,
                    )
                )
            }
            for node in flow_record.flow_json.get("nodes", []):
                node_type = node.get("type")
                if node_type not in {"part", "assembly"}:
                    continue
                procedure_ids = origin_route_procedure_ids(
                    flow_record.flow_json,
                    node["id"],
                    set(procedures_by_id),
                )
                if not procedure_ids:
                    continue
                bom = boms.get(node.get("bom_item_id")) if node_type == "part" else None
                if node_type == "part" and bom is None:
                    continue
                part_name = bom.part_name if bom else (
                    node.get("output_name") or node.get("label") or "装配体"
                )
                part_no = bom.part_no if bom else part_name
                searchable = " ".join((
                    product.product_name,
                    product.factory_code,
                    part_name,
                    part_no,
                )).lower()
                if value and value.lower() not in searchable:
                    continue
                candidates.append({
                    "product": product,
                    "bom": bom,
                    "origin_flow_node_id": node["id"],
                    "part_name": part_name,
                    "part_no": part_no,
                    "procedure_ids": procedure_ids,
                })

        total = len(candidates)
        selected = candidates[(page - 1) * page_size:page * page_size]
        selected_procedure_ids = {
            procedure_id
            for candidate in selected
            for procedure_id in candidate["procedure_ids"]
        }
        tags_by_procedure: dict[int, list[ProcedureTag]] = defaultdict(list)
        if selected_procedure_ids:
            for tag in session.scalars(
                select(ProcedureTag)
                .where(ProcedureTag.procedure_id.in_(selected_procedure_ids))
                .order_by(ProcedureTag.tag_name, ProcedureTag.id)
            ):
                tags_by_procedure[tag.procedure_id].append(tag)
        prices = {
            (
                item.product_id,
                item.product_version,
                item.origin_flow_node_id,
                item.procedure_tag_id,
            ): item.unit_price
            for item in session.scalars(
                select(ProcedureTagPrice).where(ProcedureTagPrice.product_id.in_(
                    {candidate["product"].id for candidate in selected}
                ))
            )
        } if selected else {}
        locked_configs = set(session.execute(
            select(
                ProductionItem.product_id,
                ProductionItem.product_version,
                ProductionItem.origin_flow_node_id,
                WorkOrder.procedure_id,
            )
            .join(WorkOrder, WorkOrder.production_item_id == ProductionItem.id)
            .where(
                ProductionItem.product_id.in_(
                    {candidate["product"].id for candidate in selected}
                ),
                WorkOrder.procedure_id.in_(selected_procedure_ids),
            )
        ).all()) if selected and selected_procedure_ids else set()

        data = []
        for candidate in selected:
            product = candidate["product"]
            bom = candidate["bom"]
            origin_id = candidate["origin_flow_node_id"]
            procedure_data = []
            for procedure_id in candidate["procedure_ids"]:
                procedure = procedures_by_id[procedure_id]
                available_tags = [
                    {
                        "id": tag.id,
                        "tag_name": tag.tag_name,
                        "unit_price": prices.get((
                            product.id,
                            product.version,
                            origin_id,
                            tag.id,
                        )),
                    }
                    for tag in tags_by_procedure.get(procedure_id, [])
                ]
                procedure_data.append({
                    "procedure_id": procedure.id,
                    "procedure_name": procedure.procedure_name,
                    "tags_locked": (
                        product.id,
                        product.version,
                        origin_id,
                        procedure.id,
                    ) in locked_configs,
                    "available_tags": available_tags,
                    "configured_tags": [
                        tag for tag in available_tags
                        if (
                            product.id,
                            product.version,
                            origin_id,
                            tag["id"],
                        ) in prices
                    ],
                })
            data.append({
                "product_id": product.id,
                "product_version": product.version,
                "product_name": product.product_name,
                "factory_code": product.factory_code,
                "product_bom_id": bom.id if bom else None,
                "origin_flow_node_id": origin_id,
                "part_name": candidate["part_name"],
                "part_no": candidate["part_no"],
                "procedures": procedure_data,
            })
        return data, total


def update_procedure_tag_prices(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    procedure_id: int,
    payload: ProcedureTagPriceUpdate,
    user_department: str,
) -> None:
    with SessionLocal.begin() as session:
        department = _department(session, department_code, user_department)
        procedure = session.get(Procedure, procedure_id, with_for_update=True)
        workshop = (
            session.get(Workshop, procedure.workshop_id)
            if procedure is not None
            else None
        )
        if (
            procedure is None
            or procedure.procedure_type != "standard"
            or workshop is None
            or workshop.department_id != department.id
        ):
            raise DomainError("procedure_tag_price_procedure_invalid", "当前工艺不属于该部门")
        product = session.get(Product, product_id)
        version = session.get(ProductVersion, (product_id, product_version))
        if product is None or version is None:
            raise DomainError("product_version_not_found", "产品版本不存在", status_code=404)
        flow_record = session.scalar(select(ProductProcessFlow).where(
            ProductProcessFlow.product_id == product_id,
            ProductProcessFlow.product_version == product_version,
        ))
        if (
            flow_record is None
            or procedure.id not in origin_route_procedure_ids(
                flow_record.flow_json,
                origin_flow_node_id,
                {procedure.id},
            )
        ):
            raise DomainError("procedure_tag_price_route_invalid", "该配件的流程不包含当前工艺")

        normalized: dict[str, Decimal | None] = {}
        for item in payload.tags:
            name = item.tag_name.strip()
            if name:
                normalized[name] = item.unit_price
        configured_names = {
            tag_name
            for tag_name, in session.execute(
                select(ProcedureTag.tag_name)
                .join(
                    ProcedureTagPrice,
                    ProcedureTagPrice.procedure_tag_id == ProcedureTag.id,
                )
                .where(
                    ProcedureTagPrice.product_id == product_id,
                    ProcedureTagPrice.product_version == product_version,
                    ProcedureTagPrice.origin_flow_node_id == origin_flow_node_id,
                    ProcedureTagPrice.procedure_id == procedure.id,
                )
            )
        }
        has_orders = session.scalar(
            select(WorkOrder.id)
            .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
            .where(
                ProductionItem.product_id == product_id,
                ProductionItem.product_version == product_version,
                ProductionItem.origin_flow_node_id == origin_flow_node_id,
                WorkOrder.procedure_id == procedure.id,
            )
            .limit(1)
        ) is not None
        if has_orders and set(normalized) != configured_names:
            raise DomainError(
                "procedure_tags_locked",
                "该配件已经开过工单，只能修改标记单价",
            )
        tags = {
            name: get_or_create_tag(session, procedure, name)
            for name in normalized
        }
        existing = list(session.scalars(
            select(ProcedureTagPrice)
            .where(
                ProcedureTagPrice.product_id == product_id,
                ProcedureTagPrice.product_version == product_version,
                ProcedureTagPrice.origin_flow_node_id == origin_flow_node_id,
                ProcedureTagPrice.procedure_id == procedure.id,
            )
            .with_for_update()
        ).all())
        retained_ids = {tag.id for tag in tags.values()}
        for item in existing:
            if item.procedure_tag_id not in retained_ids:
                session.delete(item)
        existing_by_tag = {item.procedure_tag_id: item for item in existing}
        for name, tag in tags.items():
            price = existing_by_tag.get(tag.id)
            if price is None:
                session.add(ProcedureTagPrice(
                    product_id=product_id,
                    product_version=product_version,
                    origin_flow_node_id=origin_flow_node_id,
                    procedure_id=procedure.id,
                    procedure_tag_id=tag.id,
                    unit_price=normalized[name],
                ))
            else:
                price.unit_price = normalized[name]


def _department(session, code: str, user_department: str) -> Department:
    department = session.scalar(
        select(Department).where(Department.department_code == code)
    )
    if department is None:
        raise DomainError("department_not_found", "部门不存在", status_code=404)
    if user_department not in {"sys", code}:
        raise DomainError("department_access_denied", "无权维护该部门配置", status_code=403)
    return department
