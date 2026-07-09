from sqlalchemy import select
from sqlalchemy.orm import Session

from models.engineering import ProductBom
from models.production import ProductionItem
from models.sales import CustomerOrderItem
from services.errors import DomainError


def is_base_info_editable(session: Session, product_id: int) -> bool:
    return not session.scalar(
        select(CustomerOrderItem.id)
        .where(CustomerOrderItem.product_id == product_id)
        .limit(1)
    )


def is_product_version_in_order(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return bool(
        session.scalar(
            select(CustomerOrderItem.id)
            .where(
                CustomerOrderItem.product_id == product_id,
                CustomerOrderItem.product_version == product_version,
            )
            .limit(1)
        )
    )


def is_product_version_in_production(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return bool(
        session.scalar(
            select(ProductionItem.id)
            .join(ProductBom, ProductBom.id == ProductionItem.product_bom_id)
            .where(
                ProductBom.product_id == product_id,
                ProductBom.product_version == product_version,
            )
            .limit(1)
        )
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
