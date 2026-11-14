from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from zzerp.modules.engineering.command_support import command_result, ensure_appearance_exists
from zzerp.modules.engineering.contracts import (
    BomItemPayload,
    CreateProductPayload,
    EngineeringCollaborators,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from zzerp.modules.engineering.editability import (
    ensure_base_info_editable,
    is_base_info_editable,
)
from zzerp.modules.engineering.handoff_routes import ensure_handoffs_preserved
from zzerp.modules.engineering.persistence import Product, ProductAppearance
from zzerp.modules.engineering.repository import EngineeringProductRepository
from zzerp.modules.engineering.routing import (
    ensure_bom_nodes_retained,
    ensure_recorded_inputs_preserved,
    ensure_referenced_bom_identity,
    ensure_referenced_routes_preserved,
    validate_nodes,
)
from zzerp.modules.engineering.rules import validate_bom_identity, validate_expected_revision
from zzerp.modules.engineering.support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from zzerp.modules.sales.api import resolve_customer
from zzerp.time import utc_now


def create_product(session: Session, payload: CreateProductPayload) -> dict:
    try:
        repository = EngineeringProductRepository(session)
        items = bom_commands(payload.bom_items)
        validate_bom_identity(items, existing_ids=set())
        customer = resolve_customer(
            session,
            payload.customer_id,
            payload.customer_name,
            allow_create=True,
        )
        product = Product(
            customer_id=customer.id,
            product_name=payload.product_name,
            factory_code=payload.factory_code,
            customer_code=payload.customer_code,
        )
        product.appearances.append(ProductAppearance(appearance_name=payload.appearance_name))
        repository.add(product)
        repository.flush()
        repository.replace_bom(product, items)
        repository.set_process_flow(product, product.appearances[0].id, empty_process_flow())
        return command_result(repository, product, base_info_editable=True)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(
    session: Session,
    product_id: int,
    payload: UpdateProductPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        repository = EngineeringProductRepository(session)
        product = repository.require(product_id, lock=True)
        validate_expected_revision(product.revision, payload.expected_revision)
        customer = resolve_customer(
            session,
            payload.customer_id,
            payload.customer_name,
            allow_create=True,
        )
        unchanged = (
            product.customer_id == customer.id
            and product.product_name == payload.product_name
            and product.factory_code == payload.factory_code
            and product.customer_code == payload.customer_code
        )
        if unchanged:
            return command_result(
                repository,
                product,
                base_info_editable=is_base_info_editable(session, product.id, collaborators),
            )
        ensure_base_info_editable(session, product.id, collaborators)
        product.customer_id = customer.id
        product.product_name = payload.product_name
        product.factory_code = payload.factory_code
        product.customer_code = payload.customer_code
        product.updated_at = utc_now()
        product.revision += 1
        return command_result(
            repository,
            product,
            base_info_editable=is_base_info_editable(session, product.id, collaborators),
        )
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def replace_product_bom(
    session: Session,
    product_id: int,
    expected_revision: int,
    items: list[BomItemPayload],
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        repository = EngineeringProductRepository(session)
        product = repository.require(product_id, lock=True)
        validate_expected_revision(product.revision, expected_revision)
        commands = bom_commands(items)
        retained_ids = validate_bom_identity(
            commands,
            {item.id for item in product.bom_items},
        )
        ensure_bom_nodes_retained(product, retained_ids)
        for appearance in product.appearances:
            ensure_referenced_bom_identity(
                session,
                product,
                appearance.id,
                commands,
                collaborators.referenced_route_pairs(session, product.id, appearance.id),
            )
        repository.replace_bom(product, commands)
        product.updated_at = utc_now()
        product.revision += 1
        return command_result(
            repository,
            product,
            base_info_editable=is_base_info_editable(session, product.id, collaborators),
        )
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    session: Session,
    product_id: int,
    expected_revision: int,
    appearance_id: int,
    process_flow: ProcessFlowPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        repository = EngineeringProductRepository(session)
        product = repository.require(product_id, lock=True)
        validate_expected_revision(product.revision, expected_revision)
        ensure_appearance_exists(product, appearance_id)
        process_flow = validate_nodes(session, product.id, process_flow)
        ensure_handoffs_preserved(
            process_flow, collaborators.referenced_handoff_pairs(session, product.id, appearance_id)
        )
        ensure_recorded_inputs_preserved(
            product,
            appearance_id,
            process_flow,
            collaborators.referenced_input_nodes(session, product.id, appearance_id),
        )
        ensure_referenced_routes_preserved(
            session,
            product,
            appearance_id,
            process_flow,
            collaborators.referenced_route_pairs(session, product.id, appearance_id),
        )
        validated = validated_flow(process_flow)
        repository.set_process_flow(
            product,
            appearance_id,
            validated,
        )
        repository.flush()
        product.updated_at = utc_now()
        product.revision += 1
        return command_result(
            repository,
            product,
            appearance_id,
            base_info_editable=is_base_info_editable(session, product.id, collaborators),
        )
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def save_product_process_flow_draft(
    session: Session,
    product_id: int,
    expected_revision: int,
    appearance_id: int,
    process_flow: ProcessFlowPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        repository = EngineeringProductRepository(session)
        product = repository.require(product_id, lock=True)
        validate_expected_revision(product.revision, expected_revision)
        ensure_appearance_exists(product, appearance_id)
        process_flow = validate_nodes(session, product.id, process_flow)
        validated = validated_flow(process_flow)
        repository.set_process_flow_draft(product, appearance_id, validated)
        repository.flush()
        product.updated_at = utc_now()
        product.revision += 1
        return command_result(
            repository,
            product,
            appearance_id,
            base_info_editable=is_base_info_editable(session, product.id, collaborators),
        )
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)
