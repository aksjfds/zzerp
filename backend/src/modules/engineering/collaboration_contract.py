from typing import Protocol

from sqlalchemy.orm import Session


class EngineeringCollaborators(Protocol):
    def has_product_reference(self, session: Session, product_id: int) -> bool: ...

    def referenced_route_pairs(self, session: Session, product_id: int) -> set[tuple[str, str]]: ...
