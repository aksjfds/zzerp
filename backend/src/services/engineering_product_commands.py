from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_version
from models.engineering import Product
from repositories.engineering_products import EngineeringProductRepository
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from services.engineering_product_mapper import serialize_product_detail
from services.engineering_product_support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from services.errors import product_not_found
from services.process_flow_mapping import synchronize_part_metadata


def _result(repository: EngineeringProductRepository, product: Product) -> dict:
    repository.flush()
    return serialize_product_detail(product, empty_process_flow())


def create_product(payload: CreateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            items = bom_commands(payload.bom_items)
            validate_bom_identity(items, existing_ids=set())
            product = Product(
                customer_name=payload.customer_name,
                product_name=payload.product_name,
                factory_code=payload.factory_code,
                customer_code=payload.customer_code,
            )
            repository.add(product)
            repository.flush()
            repository.replace_bom(product, items)
            repository.set_process_flow(product, empty_process_flow())
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(product_id: int, payload: UpdateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            validate_expected_version(product.version, payload.expected_version)
            product.customer_name = payload.customer_name
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = datetime.now()
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def replace_product_bom(
    product_id: int,
    expected_version: int,
    items: list[BomItemPayload],
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            validate_expected_version(product.version, expected_version)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands, {item.id for item in product.bom_items}
            )
            current_flow = None
            if product.process_flow is not None:
                current_flow = ProcessFlowPayload.model_validate(product.process_flow.flow_json)
                validated_flow(current_flow, retained_ids)
            saved_items = repository.replace_bom(product, commands)
            if current_flow is not None:
                synchronized = synchronize_part_metadata(
                    current_flow,
                    {item.id: (item.part_name, item.part_no) for item in saved_items},
                )
                repository.set_process_flow(
                    product, synchronized.model_dump(exclude_none=True)
                )
            product.updated_at = datetime.now()
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    product_id: int,
    expected_version: int,
    process_flow: ProcessFlowPayload,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            validate_expected_version(product.version, expected_version)
            flow = synchronize_part_metadata(
                process_flow,
                {item.id: (item.part_name, item.part_no) for item in product.bom_items},
            )
            repository.set_process_flow(
                product, validated_flow(flow, {item.id for item in product.bom_items})
            )
            product.updated_at = datetime.now()
            return _result(repository, product)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def delete_product(product_id: int, expected_version: int) -> None:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            validate_expected_version(product.version, expected_version)
            repository.delete(product)
    except StaleDataError as exc:
        raise_stale_data_error(exc)
