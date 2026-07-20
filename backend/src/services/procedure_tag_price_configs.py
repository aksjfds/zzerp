from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, or_, select

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow
from models.organization import (
    Department,
    Procedure,
    ProcedureTag,
    ProcedureTagPrice,
    Workshop,
)
from schemas.procedure_tag_prices import ProcedureTagPriceUpdate
from services.errors import DomainError
from services.procedure_tags import get_or_create_tag
from services.production_flow import part_route_procedure_ids


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
            select(Product, ProductBom, ProductProcessFlow)
            .join(
                ProductBom,
                and_(
                    ProductBom.product_id == Product.id,
                    ProductBom.product_version == Product.version,
                ),
            )
            .join(
                ProductProcessFlow,
                and_(
                    ProductProcessFlow.product_id == Product.id,
                    ProductProcessFlow.product_version == Product.version,
                ),
            )
            .order_by(Product.updated_at.desc(), Product.id.desc(), ProductBom.sort_order)
        )
        value = (keyword or "").strip()
        if value:
            pattern = f"%{value}%"
            statement = statement.where(or_(
                Product.product_name.ilike(pattern),
                Product.factory_code.ilike(pattern),
                ProductBom.part_name.ilike(pattern),
                ProductBom.part_no.ilike(pattern),
            ))

        candidates: list[tuple[Product, ProductBom, list[int]]] = []
        for product, bom, flow_record in session.execute(statement):
            procedure_ids = part_route_procedure_ids(
                flow_record.flow_json,
                bom.id,
                set(procedures_by_id),
            )
            if procedure_ids:
                candidates.append((product, bom, procedure_ids))

        total = len(candidates)
        selected = candidates[(page - 1) * page_size:page * page_size]
        bom_ids = [bom.id for _, bom, _ in selected]
        selected_procedure_ids = {
            procedure_id
            for _, _, procedure_ids in selected
            for procedure_id in procedure_ids
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
            (item.product_bom_id, item.procedure_tag_id): item.unit_price
            for item in session.scalars(
                select(ProcedureTagPrice).where(
                    ProcedureTagPrice.product_bom_id.in_(bom_ids)
                )
            )
        } if bom_ids else {}

        data = []
        for product, bom, procedure_ids in selected:
            procedure_data = []
            for procedure_id in procedure_ids:
                procedure = procedures_by_id[procedure_id]
                available_tags = [
                    {
                        "id": tag.id,
                        "tag_name": tag.tag_name,
                        "unit_price": prices.get((bom.id, tag.id)),
                    }
                    for tag in tags_by_procedure.get(procedure_id, [])
                ]
                procedure_data.append({
                    "procedure_id": procedure.id,
                    "procedure_name": procedure.procedure_name,
                    "available_tags": available_tags,
                    "configured_tags": [
                        tag for tag in available_tags
                        if (bom.id, tag["id"]) in prices
                    ],
                })
            data.append({
                "product_id": product.id,
                "product_version": product.version,
                "product_name": product.product_name,
                "factory_code": product.factory_code,
                "product_bom_id": bom.id,
                "part_name": bom.part_name,
                "part_no": bom.part_no,
                "procedures": procedure_data,
            })
        return data, total


def update_procedure_tag_prices(
    department_code: str,
    product_bom_id: int,
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
        bom = session.get(ProductBom, product_bom_id, with_for_update=True)
        if bom is None:
            raise DomainError("product_bom_not_found", "配件不存在", status_code=404)
        flow_record = session.scalar(select(ProductProcessFlow).where(
            ProductProcessFlow.product_id == bom.product_id,
            ProductProcessFlow.product_version == bom.product_version,
        ))
        if (
            flow_record is None
            or procedure.id not in part_route_procedure_ids(
                flow_record.flow_json,
                bom.id,
                {procedure.id},
            )
        ):
            raise DomainError("procedure_tag_price_route_invalid", "该配件的流程不包含当前工艺")

        normalized: dict[str, Decimal | None] = {}
        for item in payload.tags:
            name = item.tag_name.strip()
            if name:
                normalized[name] = item.unit_price
        tags = {
            name: get_or_create_tag(session, procedure, name)
            for name in normalized
        }
        existing = list(session.scalars(
            select(ProcedureTagPrice)
            .where(
                ProcedureTagPrice.product_bom_id == bom.id,
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
                    product_bom_id=bom.id,
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

