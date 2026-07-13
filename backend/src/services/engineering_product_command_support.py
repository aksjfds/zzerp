from models.engineering import Product
from repositories.engineering_products import EngineeringProductRepository
from services.engineering_product_mapper import serialize_product_detail
from services.engineering_product_support import empty_process_flow
from services.errors import product_not_found


def command_result(
    repository: EngineeringProductRepository,
    product: Product,
    requested_version: int | None = None,
) -> dict:
    repository.flush()
    return serialize_product_detail(product, empty_process_flow(), requested_version)


def product_versions(product: Product) -> set[int]:
    return {
        item.product_version for item in product.bom_items
    } | {
        item.product_version for item in product.process_flows
    }


def ensure_version_exists(product: Product, product_version: int) -> None:
    if product_version not in product_versions(product):
        raise product_not_found()
