from modules.engineering import command_api as engineering
from modules.engineering.api import get_product as query_product
from modules.inventory import reference_api as inventory_references
from modules.production_core import reference_api as production_references
from modules.sales import reference_api as sales_references
from modules.standard_execution import pricing_api, reference_api as pricing_references


class _EngineeringCollaborators:
    has_product_reference = staticmethod(sales_references.has_product_reference)
    has_product_version_reference = staticmethod(sales_references.has_product_version_reference)
    has_product_version_production_reference = staticmethod(
        production_references.has_product_version_production_reference
    )
    has_product_version_inventory_reference = staticmethod(
        inventory_references.has_product_version_inventory_reference
    )
    product_version_procedure_price_references = staticmethod(
        pricing_references.product_version_procedure_price_references
    )
    copy_product_version_prices = staticmethod(pricing_api.copy_product_version_prices)


COLLABORATORS = _EngineeringCollaborators()


def get_product(product_id, version=None):
    return query_product(product_id, version, COLLABORATORS)


def update_product_info(product_id, payload):
    return engineering.update_product_info(product_id, payload, COLLABORATORS)


def replace_product_bom(product_id, expected_revision, product_version, items):
    return engineering.replace_product_bom(
        product_id, expected_revision, product_version, items, COLLABORATORS
    )


def update_product_process_flow(product_id, expected_revision, product_version, flow):
    return engineering.update_product_process_flow(
        product_id, expected_revision, product_version, flow, COLLABORATORS
    )


def save_product_process_flow_draft(product_id, expected_revision, product_version, flow):
    return engineering.save_product_process_flow_draft(
        product_id, expected_revision, product_version, flow, COLLABORATORS
    )


def create_product_version(product_id, expected_revision, source_version=None):
    return engineering.create_product_version(
        product_id, expected_revision, COLLABORATORS, source_version
    )


__all__ = [
    "create_product_version",
    "get_product",
    "replace_product_bom",
    "save_product_process_flow_draft",
    "update_product_info",
    "update_product_process_flow",
]
