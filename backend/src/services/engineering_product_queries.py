from database import SessionLocal
from repositories.engineering_products import EngineeringProductRepository
from services.engineering_product_mapper import (
    serialize_product_detail,
    serialize_product_summary,
)
from services.engineering_product_support import empty_process_flow
from services.errors import product_not_found


def list_products(
    page: int, page_size: int, keyword: str | None = None
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = EngineeringProductRepository(session)
        data = [
            serialize_product_summary(product, bom_count)
            for product, bom_count in repository.list_with_bom_counts(
                (page - 1) * page_size, page_size, keyword
            )
        ]
        return data, repository.count(keyword)


def get_product(product_id: int, version: int | None = None) -> dict:
    with SessionLocal() as session:
        product = EngineeringProductRepository(session).get(product_id)
        if product is None:
            raise product_not_found()
        requested_version = version or product.version
        available_versions = {
            item.product_version for item in product.process_flows
        } | {item.product_version for item in product.bom_items}
        if requested_version not in available_versions:
            raise product_not_found()
        return serialize_product_detail(product, empty_process_flow(), requested_version)


def list_product_versions(product_id: int) -> list[int]:
    with SessionLocal() as session:
        product = EngineeringProductRepository(session).get(product_id)
        if product is None:
            raise product_not_found()
        return sorted(
            {item.product_version for item in product.process_flows}
            | {item.product_version for item in product.bom_items},
            reverse=True,
        )
