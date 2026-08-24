from typing import Protocol

from sqlalchemy.orm import Session


class EngineeringCollaborators(Protocol):
    def has_product_reference(self, session: Session, product_id: int) -> bool: ...

    def has_product_version_reference(
        self, session: Session, product_id: int, product_version: int
    ) -> bool: ...

    def has_product_version_production_reference(
        self, session: Session, product_id: int, product_version: int
    ) -> bool: ...

    def has_product_version_inventory_reference(
        self, session: Session, product_id: int, product_version: int
    ) -> bool: ...

    def product_version_procedure_price_references(
        self, session: Session, product_id: int, product_version: int
    ) -> list[tuple[str, str]]: ...

    def copy_product_version_prices(
        self,
        session: Session,
        *,
        product_id: int,
        source_version: int,
        target_version: int,
        bom_id_map: dict[int, int],
    ) -> None: ...


__all__ = ["EngineeringCollaborators"]
