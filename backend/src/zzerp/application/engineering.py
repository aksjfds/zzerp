from zzerp.modules.engineering import api as engineering
from zzerp.modules.planning.api import (
    has_product_reference,
    referenced_handoff_pairs,
    referenced_input_nodes,
    referenced_route_pairs,
)


class _EngineeringCollaborators:
    has_product_reference = staticmethod(has_product_reference)
    referenced_route_pairs = staticmethod(referenced_route_pairs)
    referenced_handoff_pairs = staticmethod(referenced_handoff_pairs)
    referenced_input_nodes = staticmethod(referenced_input_nodes)


COLLABORATORS = _EngineeringCollaborators()


def get_product(session, product_id, appearance_id=None):
    return engineering.get_product(session, product_id, appearance_id, COLLABORATORS)


def update_product_info(session, product_id, payload):
    return engineering.update_product_info(session, product_id, payload, COLLABORATORS)


def replace_product_bom(session, product_id, expected_revision, items):
    return engineering.replace_product_bom(
        session, product_id, expected_revision, items, COLLABORATORS
    )


def update_product_process_flow(session, product_id, expected_revision, appearance_id, flow):
    return engineering.update_product_process_flow(
        session, product_id, expected_revision, appearance_id, flow, COLLABORATORS
    )


def save_product_process_flow_draft(session, product_id, expected_revision, appearance_id, flow):
    return engineering.save_product_process_flow_draft(
        session, product_id, expected_revision, appearance_id, flow, COLLABORATORS
    )


def save_product_appearance(session, product_id, payload, appearance_id=None):
    return engineering.save_product_appearance(
        session, product_id, payload, COLLABORATORS, appearance_id
    )
