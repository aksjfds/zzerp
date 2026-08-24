"""Database filters shared by current and historical production cards."""

from sqlalchemy import and_, or_
from modules.engineering.model_api import Product, ProductBom
from modules.production_core.model_api import ProductionItem

def source_keyword_filter(keyword: str | None):
    value = (keyword or "").strip().lower()
    if not value:
        return None
    tokens = [
        item
        for item in value.removesuffix("装配体").replace("-", " ").split()
        if item
    ]
    searchable_columns = (
        Product.product_name,
        Product.factory_code,
        ProductBom.part_name,
        ProductBom.part_no,
    )
    token_filter = and_(
        *[
            or_(*(column.ilike(f"%{token}%") for column in searchable_columns))
            for token in tokens
        ]
    ) if tokens else None
    return (
        or_(ProductionItem.product_bom_id.is_(None), token_filter)
        if token_filter is not None
        else None
    )

__all__ = ["source_keyword_filter"]
