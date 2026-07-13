from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from models.engineering import Product
from models.organization import Procedure
from repositories.engineering_products import EngineeringProductRepository
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from services.engineering_product_command_support import command_result, ensure_version_exists
from services.engineering_product_editability import (
    ensure_base_info_editable,
    ensure_product_version_editable,
)
from services.engineering_product_support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from services.errors import DomainError, product_not_found
from services.process_flow_mapping import synchronize_part_metadata

def _ensure_procedures_exist(session, flow: ProcessFlowPayload) -> None:
    procedure_ids = {
        node.procedure_id for node in flow.nodes if node.type == "process"
    }
    if not procedure_ids:
        return
    existing_ids = set(
        session.scalars(select(Procedure.id).where(Procedure.id.in_(procedure_ids))).all()
    )
    if existing_ids != procedure_ids:
        raise DomainError(
            "process_procedure_invalid",
            "流程图引用了不存在的工艺",
            path="process_flow.nodes",
        )


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
            repository.replace_bom(product, product.version, items)
            repository.set_process_flow(product, product.version, empty_process_flow())
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(product_id: int, payload: UpdateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, payload.expected_revision)
            unchanged = (
                product.customer_name == payload.customer_name
                and product.product_name == payload.product_name
                and product.factory_code == payload.factory_code
                and product.customer_code == payload.customer_code
            )
            if unchanged:
                return command_result(repository, product)
            ensure_base_info_editable(session, product.id)
            product.customer_name = payload.customer_name
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = datetime.now()
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
            ensure_product_version_editable(session, product.id, product_version)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            current_flow = None
            process_flow_record = next(
                (
                    item
                    for item in product.process_flows
                    if item.product_version == product_version
                ),
                None,
            )
            if process_flow_record is not None:
                current_flow = ProcessFlowPayload.model_validate(
                    process_flow_record.flow_json
                )
                validated_flow(current_flow, retained_ids)
            saved_items = repository.replace_bom(product, product_version, commands)
            if current_flow is not None:
                synchronized = synchronize_part_metadata(
                    current_flow,
                    {item.id: (item.part_name, item.part_no) for item in saved_items},
                )
                repository.set_process_flow(
                    product,
                    product_version,
                    synchronized.model_dump(exclude_none=True),
                )
            product.updated_at = datetime.now()
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
            ensure_product_version_editable(session, product.id, product_version)
            flow = synchronize_part_metadata(
                process_flow,
                {
                    item.id: (item.part_name, item.part_no)
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            _ensure_procedures_exist(session, flow)
            repository.set_process_flow(
                product,
                product_version,
                validated_flow(
                    flow,
                    {
                        item.id
                        for item in product.bom_items
                        if item.product_version == product_version
                    },
                ),
            )
            product.updated_at = datetime.now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def delete_product(product_id: int, expected_revision: int) -> None:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            repository.delete(product)
    except IntegrityError as exc:
        raise DomainError(
            "product_in_use",
            "产品已被客户订单引用，不能删除",
            status_code=409,
        ) from exc
    except StaleDataError as exc:
        raise_stale_data_error(exc)
