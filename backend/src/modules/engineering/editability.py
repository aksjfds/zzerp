from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.engineering.persistence import ProductBom
from modules.errors import DomainError
from modules.production_core.reference_api import has_production_items_for_boms
from modules.sales.reference_api import (
    has_product_reference,
    has_product_version_reference,
)


def is_base_info_editable(session: Session, product_id: int) -> bool:
    return not has_product_reference(session, product_id)


def is_product_version_in_order(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return has_product_version_reference(session, product_id, product_version)


def is_product_version_in_production(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    product_bom_ids = session.scalars(
        select(ProductBom.id).where(
            ProductBom.product_id == product_id,
            ProductBom.product_version == product_version,
        )
    ).all()
    return has_production_items_for_boms(
        session,
        product_bom_ids,
    )


def is_product_version_editable(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return not is_product_version_in_order(
        session,
        product_id,
        product_version,
    ) and not is_product_version_in_production(
        session,
        product_id,
        product_version,
    )


def ensure_base_info_editable(session: Session, product_id: int) -> None:
    if not is_base_info_editable(session, product_id):
        raise DomainError(
            "product_info_in_use",
            "产品已被客户订单引用，基础信息不允许修改",
            status_code=409,
        )


def ensure_product_version_editable(
    session: Session,
    product_id: int,
    product_version: int,
) -> None:
    if is_product_version_in_order(session, product_id, product_version):
        raise DomainError(
            "product_version_in_use",
            "当前产品版本已被客户订单引用，请创建新版本后修改",
            status_code=409,
        )
    if is_product_version_in_production(session, product_id, product_version):
        raise DomainError(
            "product_version_in_production",
            "当前产品版本已有生产记录，不能修改或删除",
            status_code=409,
        )
