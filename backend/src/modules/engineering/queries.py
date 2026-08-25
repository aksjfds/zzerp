from database import SessionLocal
from modules.engineering.collaboration_contract import EngineeringCollaborators
from modules.engineering.editability import (
    is_base_info_editable,
    is_product_version_editable,
)
from modules.engineering.mapper import (
    serialize_product_detail,
    serialize_product_summary,
)
from modules.engineering.product_reference_api import get_product_order_readinesses
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import empty_process_flow
from modules.errors import product_not_found
from modules.sales.customer_api import customer_names_by_ids


def list_products(
    page: int,
    page_size: int,
    keyword: str | None = None,
    customer_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = EngineeringProductRepository(session)
        products_with_counts = repository.list_with_bom_counts(
            (page - 1) * page_size, page_size, keyword, customer_id
        )
        customer_names = customer_names_by_ids(
            session,
            {product.customer_id for product, _ in products_with_counts},
        )
        readiness = get_product_order_readinesses(
            session,
            [product for product, _ in products_with_counts],
        )
        data = [
            serialize_product_summary(
                product,
                bom_count,
                customer_names[product.customer_id],
                order_ready=readiness[product.id].ready,
                order_ready_reason=readiness[product.id].reason,
            )
            for product, bom_count in products_with_counts
        ]
        return data, repository.count(keyword, customer_id)


def get_product(
    product_id: int,
    version: int | None,
    collaborators: EngineeringCollaborators,
) -> dict:
    with SessionLocal() as session:
        product = EngineeringProductRepository(session).get(product_id)
        if product is None:
            raise product_not_found()
        requested_version = version or product.version
        available_versions = {item.version for item in product.versions}
        if requested_version not in available_versions:
            raise product_not_found()
        customer_names = customer_names_by_ids(session, {product.customer_id})
        readiness = get_product_order_readinesses(session, [product])[product.id]
        return serialize_product_detail(
            product,
            empty_process_flow(),
            requested_version,
            customer_name=customer_names[product.customer_id],
            order_ready=readiness.ready,
            order_ready_reason=readiness.reason,
            base_info_editable=is_base_info_editable(
                session,
                product_id,
                collaborators,
            ),
            version_editable=is_product_version_editable(
                session,
                product_id,
                requested_version,
                collaborators,
            ),
        )


def list_product_versions(product_id: int) -> list[int]:
    with SessionLocal() as session:
        product = EngineeringProductRepository(session).get(product_id)
        if product is None:
            raise product_not_found()
        return sorted((item.version for item in product.versions), reverse=True)
