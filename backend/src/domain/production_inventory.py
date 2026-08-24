"""Immutable values exchanged while issuing plan inventory into production."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssuedPlanItem:
    id: int
    customer_order_item_id: int
    product_id: int
    product_version: int
    item_type: str
    product_bom_id: int | None
    flow_node_id: str


@dataclass(frozen=True, slots=True)
class IssuedInventoryStock:
    reservation_id: int
    production_plan_item_id: int
    stock_id: int
    product_id: int
    product_version: int
    flow_node_id: str
    completed_flow_node_id: str
    quantity: int
    quantity_before: int
    quantity_after: int
    reserved_before: int
    reserved_after: int


__all__ = ["IssuedInventoryStock", "IssuedPlanItem"]
