"""Persistence-free collaborators required by customer-order workflows."""

from collections.abc import Collection
from typing import Any, Protocol

from domain.product import ProductReference


class SalesEngineeringPort(Protocol):
    def get_product_references(
        self,
        session: Any,
        product_ids: Collection[int],
    ) -> dict[int, ProductReference]: ...

    def resolve_order_product_references(
        self,
        session: Any,
        product_ids: Collection[int],
        customer_id: int,
    ) -> dict[int, ProductReference]: ...


class SalesProductionPort(Protocol):
    def order_item_shipped_quantities(
        self,
        session: Any,
        customer_order_item_ids: Collection[int],
    ) -> dict[int, int]: ...

    def load_product_flow(
        self,
        session: Any,
        product_id: int,
        product_version: int,
    ) -> tuple[dict, dict[str, dict]]: ...

    def shipping_node_and_unit_quantity(
        self,
        session: Any,
        flow: dict,
        nodes: dict[str, dict],
    ) -> tuple[dict, int]: ...


__all__ = ["SalesEngineeringPort", "SalesProductionPort"]
