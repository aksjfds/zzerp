from sqlalchemy.orm import Session

from zzerp.modules.engineering.command_support import ensure_appearance_exists
from zzerp.modules.engineering.contracts import EngineeringCollaborators
from zzerp.modules.engineering.editability import (
    is_base_info_editable,
)
from zzerp.modules.engineering.mapper import (
    serialize_product_detail,
    serialize_product_summary,
)
from zzerp.modules.engineering.readiness import get_product_design_readinesses
from zzerp.modules.engineering.repository import EngineeringProductRepository
from zzerp.modules.engineering.support import empty_process_flow
from zzerp.modules.sales.api import customer_names_by_ids


def list_products(
    session: Session,
    page: int,
    page_size: int,
    keyword: str | None = None,
    customer_id: int | None = None,
) -> tuple[list[dict], int]:
    repository = EngineeringProductRepository(session)
    products_with_counts = repository.list_with_bom_counts(
        (page - 1) * page_size, page_size, keyword, customer_id
    )
    customer_names = customer_names_by_ids(
        session,
        {product.customer_id for product, _ in products_with_counts},
    )
    readiness = get_product_design_readinesses(
        session,
        [product for product, _ in products_with_counts],
    )
    data = [
        serialize_product_summary(
            product,
            bom_count,
            customer_names[product.customer_id],
            design_ready=readiness[product.id].ready,
            design_ready_reason=readiness[product.id].reason,
        )
        for product, bom_count in products_with_counts
    ]
    return data, repository.count(keyword, customer_id)


def get_product(
    session: Session,
    product_id: int,
    appearance_id: int | None,
    collaborators: EngineeringCollaborators,
) -> dict:
    product = EngineeringProductRepository(session).require(product_id)
    if appearance_id is not None:
        ensure_appearance_exists(product, appearance_id)
    customer_names = customer_names_by_ids(session, {product.customer_id})
    readiness = get_product_design_readinesses(session, [product])[product.id]
    return serialize_product_detail(
        session,
        product,
        empty_process_flow(),
        appearance_id,
        customer_name=customer_names[product.customer_id],
        design_ready=readiness.ready,
        design_ready_reason=readiness.reason,
        base_info_editable=is_base_info_editable(
            session,
            product_id,
            collaborators,
        ),
        appearance_editable=True,
    )


def list_product_appearances(session: Session, product_id: int) -> list[dict]:
    product = EngineeringProductRepository(session).require(product_id)
    return [{"id": a.id, "appearance_name": a.appearance_name} for a in product.appearances]


def list_product_options(
    session: Session, customer_id: int, keyword: str | None = None
) -> list[dict]:
    return EngineeringProductRepository(session).list_options(customer_id, keyword)
