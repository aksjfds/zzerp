from modules.engineering.persistence import Product
from modules.engineering.mapper import serialize_product_detail
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import empty_process_flow
from modules.errors import product_not_found
from modules.sales.customer_api import customer_names_by_ids


def command_result(
    repository: EngineeringProductRepository,
    product: Product,
    requested_version: int | None = None,
) -> dict:
    repository.flush()
    customer_names = customer_names_by_ids(
        repository.session,
        {product.customer_id},
    )
    return serialize_product_detail(
        product,
        empty_process_flow(),
        requested_version,
        customer_name=customer_names[product.customer_id],
    )


def product_versions(product: Product) -> set[int]:
    return {item.version for item in product.versions}


def ensure_version_exists(product: Product, product_version: int) -> None:
    if product_version not in product_versions(product):
        raise product_not_found()
