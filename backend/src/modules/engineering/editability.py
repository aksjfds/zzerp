from sqlalchemy.orm import Session

from modules.errors import DomainError
from modules.engineering.collaboration_contract import EngineeringCollaborators


def is_base_info_editable(
    session: Session,
    product_id: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return not collaborators.has_product_reference(session, product_id)


def is_product_version_in_order(
    session: Session,
    product_id: int,
    product_version: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return collaborators.has_product_version_reference(session, product_id, product_version)


def is_product_version_in_production(
    session: Session,
    product_id: int,
    product_version: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return collaborators.has_product_version_production_reference(
        session,
        product_id,
        product_version,
    )


def is_product_version_node_referenced(
    session: Session,
    product_id: int,
    product_version: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return (
        is_product_version_in_order(session, product_id, product_version, collaborators)
        or is_product_version_in_production(session, product_id, product_version, collaborators)
        or collaborators.has_product_version_inventory_reference(
            session,
            product_id,
            product_version,
        )
    )


def is_product_version_editable(
    session: Session,
    product_id: int,
    product_version: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return not is_product_version_node_referenced(session, product_id, product_version, collaborators)


def ensure_base_info_editable(
    session: Session,
    product_id: int,
    collaborators: EngineeringCollaborators,
) -> None:
    if not is_base_info_editable(session, product_id, collaborators):
        raise DomainError(
            "product_info_in_use",
            "产品已被客户订单引用，基础信息不允许修改",
            status_code=409,
        )


def ensure_product_version_editable(
    session: Session,
    product_id: int,
    product_version: int,
    collaborators: EngineeringCollaborators,
) -> None:
    if is_product_version_node_referenced(session, product_id, product_version, collaborators):
        raise DomainError(
            "product_version_in_use",
            "当前产品版本已被业务数据引用，请创建新版本后修改",
            status_code=409,
        )
