"""Stable product identity values shared across business modules."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductReference:
    id: int
    customer_id: int
    product_name: str
    factory_code: str
    customer_code: str
    version: int


__all__ = ["ProductReference"]
