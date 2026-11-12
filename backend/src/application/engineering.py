from modules.engineering import command_api as engineering
from modules.engineering.api import get_product as query_product
from modules.planning.reference_api import has_product_reference, referenced_route_pairs


class _EngineeringCollaborators:
    has_product_reference = staticmethod(has_product_reference)
    referenced_route_pairs = staticmethod(referenced_route_pairs)


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
        product_id, expected_revision, product_version, flow
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
