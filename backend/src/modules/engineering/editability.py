from sqlalchemy.orm import Session

from modules.engineering.collaboration_contract import EngineeringCollaborators
from modules.errors import DomainError


def is_base_info_editable(
    session: Session,
    product_id: int,
    collaborators: EngineeringCollaborators,
) -> bool:
    return not collaborators.has_product_reference(session, product_id)


def ensure_base_info_editable(
    session: Session,
    product_id: int,
    collaborators: EngineeringCollaborators,
) -> None:
    if not is_base_info_editable(session, product_id, collaborators):
        raise DomainError(
            "product_info_in_use",
            "产品已被生产计划引用，基础信息不允许修改",
            status_code=409,
        )
