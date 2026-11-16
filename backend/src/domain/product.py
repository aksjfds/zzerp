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


@dataclass(frozen=True, slots=True)
class SnapshotBomItem:
    id: int
    part_name: str
    part_no: str
    pcs: int
    remark: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class ProductDesignSnapshot:
    product_id: int
    source_version: int
    source_version_value: str
    product_name: str
    factory_code: str
    customer_code: str
    bom_snapshot: tuple[SnapshotBomItem, ...]
    process_flow_snapshot: dict[str, object]


__all__ = ["ProductDesignSnapshot", "ProductReference", "SnapshotBomItem"]
