"""Parallel named appearances share product BOM and never activate or replace another appearance."""

from copy import deepcopy

from sqlalchemy.exc import IntegrityError

from zzerp.errors import DomainError
from zzerp.modules.engineering.command_support import command_result, ensure_appearance_exists
from zzerp.modules.engineering.editability import is_base_info_editable
from zzerp.modules.engineering.persistence import ProductAppearance
from zzerp.modules.engineering.repository import EngineeringProductRepository
from zzerp.modules.engineering.rules import validate_expected_revision
from zzerp.modules.engineering.support import empty_process_flow, raise_integrity_error
from zzerp.time import utc_now


def save_product_appearance(session, product_id, payload, collaborators, appearance_id=None):
    try:
        repository = EngineeringProductRepository(session)
        product = repository.require(product_id, lock=True)
        validate_expected_revision(product.revision, payload.expected_revision)
        if appearance_id is not None:
            ensure_appearance_exists(product, appearance_id)
            appearance = next(a for a in product.appearances if a.id == appearance_id)
            appearance.appearance_name = payload.appearance_name
        else:
            appearance = ProductAppearance(appearance_name=payload.appearance_name)
            product.appearances.append(appearance)
            repository.flush()
            flow = empty_process_flow()
            if payload.source_appearance_id is not None:
                ensure_appearance_exists(product, payload.source_appearance_id)
                source = next(
                    (
                        f
                        for f in product.process_flows
                        if f.appearance_id == payload.source_appearance_id
                    ),
                    None,
                )
                if source is None:
                    raise DomainError(
                        "appearance_flow_missing", "来源外观缺少正式流程图", status_code=409
                    )
                flow = deepcopy(source.flow_json)
            repository.set_process_flow(product, appearance.id, flow)
        product.revision += 1
        product.updated_at = utc_now()
        return command_result(
            repository,
            product,
            appearance.id,
            base_info_editable=is_base_info_editable(session, product.id, collaborators),
        )
    except IntegrityError as exc:
        raise_integrity_error(exc)
