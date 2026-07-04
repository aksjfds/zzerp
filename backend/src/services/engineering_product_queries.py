from database import SessionLocal
from repositories.engineering_products import EngineeringProductRepository
from services.engineering_product_mapper import (
    serialize_product_detail,
    serialize_product_summary,
)
from services.engineering_product_support import empty_process_flow
from services.errors import product_not_found


def list_products() -> list[dict]:
    with SessionLocal() as session:
        repository = EngineeringProductRepository(session)
        return [
            serialize_product_summary(product, bom_count)
            for product, bom_count in repository.list_with_bom_counts()
        ]


def get_product(product_id: int) -> dict:
    with SessionLocal() as session:
        product = EngineeringProductRepository(session).get(product_id)
        if product is None:
            raise product_not_found()
        return serialize_product_detail(product, empty_process_flow())
