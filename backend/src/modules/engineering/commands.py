from sqlalchemy.exc import IntegrityError
from modules.engineering.handoff_routes import ensure_handoffs_preserved
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from domain.time import utc_now
from modules.engineering.command_support import command_result, ensure_version_exists
from modules.engineering.collaboration_contract import EngineeringCollaborators
from modules.engineering.editability import (
    ensure_base_info_editable,
)
from modules.engineering.persistence import Product, ProductVersion
from modules.engineering.routing import (
    ensure_bom_nodes_retained, ensure_referenced_bom_identity,
    ensure_referenced_routes_preserved, ensure_recorded_inputs_preserved, validate_nodes,
)
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from modules.errors import product_not_found
from modules.sales.customer_api import resolve_customer


def create_product(payload: CreateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
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
            product.versions.append(ProductVersion(version=1))
            repository.add(product)
            repository.flush()
            repository.replace_bom(product, product.version, items)
            repository.set_process_flow(product, product.version, empty_process_flow())
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(
    product_id: int,
    payload: UpdateProductPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
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
                return command_result(repository, product)
            ensure_base_info_editable(session, product.id, collaborators)
            product.customer_id = customer.id
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)

def replace_product_bom(
    product_id: int,
    expected_revision: int,
    product_version: int,
    items: list[BomItemPayload],
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands,
                {item.id for item in product.bom_items if item.product_version == product_version},
            )
            ensure_bom_nodes_retained(product, product_version, retained_ids)
            ensure_referenced_bom_identity(
                session, product, product_version, commands,
                collaborators.referenced_route_pairs(session, product.id),
            )
            repository.replace_bom(product, product_version, commands)
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    product_id: int,
    expected_revision: int,
    product_version: int,
    process_flow: ProcessFlowPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            process_flow = validate_nodes(session, product.id, product_version, process_flow)
            if product_version == product.version:
                ensure_handoffs_preserved(process_flow, collaborators.referenced_handoff_pairs(session, product.id))
                ensure_recorded_inputs_preserved(product, process_flow, collaborators.referenced_input_nodes(session, product.id))
                ensure_referenced_routes_preserved(
                    session, product, process_flow,
                    collaborators.referenced_route_pairs(session, product.id),
                )
            validated = validated_flow(process_flow)
            repository.set_process_flow(
                product,
                product_version,
                validated,
            )
            repository.flush()
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def save_product_process_flow_draft(
    product_id: int,
    expected_revision: int,
    product_version: int,
    process_flow: ProcessFlowPayload,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            process_flow = validate_nodes(session, product.id, product_version, process_flow)
            validated = validated_flow(process_flow)
            repository.set_process_flow_draft(product, product_version, validated)
            repository.flush()
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)
