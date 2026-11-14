from zzerp.errors import DomainError
from zzerp.modules.engineering.mapper import serialize_product_detail
from zzerp.modules.engineering.persistence import Product
from zzerp.modules.engineering.readiness import get_product_design_readinesses
from zzerp.modules.engineering.repository import EngineeringProductRepository
from zzerp.modules.engineering.support import empty_process_flow
from zzerp.modules.sales.api import customer_names_by_ids


def command_result(
    repository: EngineeringProductRepository,
    product: Product,
    appearance_id: int | None = None,
    *,
    base_info_editable: bool,
) -> dict:
    repository.flush()
    customer_names = customer_names_by_ids(
        repository.session,
        {product.customer_id},
    )
    readiness = get_product_design_readinesses(repository.session, [product])[product.id]
    return serialize_product_detail(
        repository.session,
        product,
        empty_process_flow(),
        appearance_id,
        customer_name=customer_names[product.customer_id],
        design_ready=readiness.ready,
        design_ready_reason=readiness.reason,
        base_info_editable=base_info_editable,
        appearance_editable=True,
    )


def ensure_appearance_exists(product, appearance_id):
    if appearance_id not in {a.id for a in product.appearances}:
        raise DomainError("appearance_not_found", "外观不属于该产品", status_code=404)
