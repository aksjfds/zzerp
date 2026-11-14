"""Readiness of a product's parallel appearances, using only the common product BOM."""

from collections.abc import Collection
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select

from zzerp.errors import DomainError
from zzerp.modules.engineering.contracts import ProcessFlowPayload
from zzerp.modules.engineering.flow import material_routes
from zzerp.modules.engineering.persistence import Product, ProductBom, ProductProcessFlow


@dataclass(frozen=True, slots=True)
class ProductDesignReadiness:
    ready: bool
    reason: str


def _has_valid_routes(payload: dict, bom_ids: set[int]) -> bool:
    try:
        flow = ProcessFlowPayload.model_validate(payload)
        return bool(material_routes(flow)) and all(
            n.bom_item_id in bom_ids for n in flow.nodes if n.type == "part"
        )
    except (ValidationError, DomainError):
        return False


def get_product_design_readinesses(session, products: Collection[Product]):
    ids = {p.id for p in products}
    if not ids:
        return {}
    bom = {key: set() for key in ids}
    for pid, bid in session.execute(
        select(ProductBom.product_id, ProductBom.id).where(ProductBom.product_id.in_(ids))
    ):
        bom[pid].add(bid)
    flows = {key: [] for key in ids}
    for pid, payload in session.execute(
        select(ProductProcessFlow.product_id, ProductProcessFlow.flow_json).where(
            ProductProcessFlow.product_id.in_(ids)
        )
    ):
        flows[pid].append(payload)
    result = {}
    for product_id in ids:
        ready = any(_has_valid_routes(flow, bom[product_id]) for flow in flows[product_id])
        result[product_id] = ProductDesignReadiness(ready, "" if ready else "尚无可生产外观流程")
    return result
